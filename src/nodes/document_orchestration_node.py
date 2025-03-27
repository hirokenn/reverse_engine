class DocumentOrchestrationNode:
    def __init__(self, llm_service, rag_system):
        self.llm = llm_service
        self.rag_system = rag_system
        
    def process(self, groups):
        """
        グループ情報から最終ドキュメントを生成する
        
        Args:
            groups: スクリプトグループのリスト
            
        Returns:
            最終ドキュメント（目次とセクション）
        """
        # 目次と概要の生成
        table_of_contents = self._generate_table_of_contents(groups)
        
        # 各セクションのドキュメント生成
        sections = self._generate_sections(table_of_contents, groups)
        
        # 整合性チェック
        feedback = self._check_consistency(sections)
        
        # フィードバックがある場合は再生成
        if feedback and feedback != "問題なし":
            return self._regenerate_with_feedback(table_of_contents, groups, feedback)
            
        return {
            "table_of_contents": table_of_contents,
            "sections": sections
        }
    
    def _generate_table_of_contents(self, groups):
        """
        グループ情報から目次構造を生成
        
        Args:
            groups: スクリプトグループのリスト
            
        Returns:
            目次構造のリスト
        """
        # プロンプトの作成
        prompt = "以下のスクリプトグループから論理的な目次構造を作成してください。\n\n"
        
        for group in groups:
            prompt += f"## グループ: {group['name']}\n"
            prompt += f"説明: {group['description']}\n"
            prompt += "含まれるスクリプト:\n"
            
            for item in group["items"]:
                prompt += f"- {item['script_id']}\n"
            
            prompt += "\n"
        
        prompt += """
        以下の形式でJSON形式の目次を返してください:
        ```json
        [
          {
            "title": "セクションのタイトル",
            "description": "セクションの説明（1-2文）",
            "script_ids": ["script1", "script2"]
          }
        ]
        ```
        
        目次は次のルールに従ってください:
        1. 各セクションは論理的なまとまりを持ち、全体として整合性があること
        2. 全てのスクリプトが含まれること
        3. セクションの数は5〜10程度にすること
        4. セクションには番号を付けないこと（例: '1. 概要'ではなく'概要'）
        """
        
        # プロンプトを表示
        print("\n===== 目次生成 プロンプト =====")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("===== 目次生成 プロンプト終了 =====\n")
        
        # LLMに問い合わせ
        response = self.llm.invoke(prompt)
        response_text = response.content
        
        # レスポンスから目次構造を抽出
        return self._parse_toc_response(response_text)
    
    def _generate_sections(self, toc, groups):
        """
        目次に基づいて各セクションの内容を生成
        
        Args:
            toc: 目次構造
            groups: スクリプトグループ
            
        Returns:
            セクションのリスト
        """
        sections = []
        
        for section in toc:
            print(f"セクション '{section['title']}' を生成中...")
            
            # RAGシステムを使用して各セクションのコンテンツを生成
            content = self.rag_system.generate_content(
                query=section["title"],
                context=section["description"],
                document_ids=section.get("script_ids", [])
            )
            
            sections.append({
                "title": section["title"],
                "content": content
            })
            
        return sections
    
    def _check_consistency(self, sections):
        """
        セクション間の整合性をチェック
        
        Args:
            sections: ドキュメントのセクションリスト
            
        Returns:
            フィードバック（問題がなければNoneまたは「問題なし」）
        """
        # セクションの内容が少なすぎる場合のチェック
        for section in sections:
            if len(section["content"].split()) < 50:
                return f"セクション '{section['title']}' の内容が不足しています。より詳細な情報を追加してください。"
        
        # プロンプトの作成
        prompt = "以下のドキュメントセクションを確認し、整合性の問題があれば指摘してください。\n\n"
        
        for section in sections:
            prompt += f"## {section['title']}\n"
            # 内容が長い場合は省略
            content_preview = section["content"][:500] + "..." if len(section["content"]) > 500 else section["content"]
            prompt += f"{content_preview}\n\n"
        
        prompt += """
        以下の点について評価してください:
        1. 各セクション間の情報の重複や矛盾
        2. 全体としての流れの一貫性
        3. 専門用語の使用の一貫性
        4. 情報の詳細度のバランス
        
        問題がなければ「問題なし」と回答してください。問題がある場合は、具体的な問題点と改善案を示してください。
        """
        
        # プロンプトを表示
        print("\n===== 整合性チェック プロンプト =====")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("===== 整合性チェック プロンプト終了 =====\n")
        
        # LLMに問い合わせ
        response = self.llm.invoke(prompt)
        feedback = response.content.strip()
        
        # 「問題なし」の場合はNoneを返す
        if "問題なし" in feedback or "問題は見つかりませんでした" in feedback:
            return "問題なし"
            
        return feedback
    
    def _regenerate_with_feedback(self, toc, groups, feedback):
        """
        フィードバックを元にドキュメントを再生成
        
        Args:
            toc: 目次構造
            groups: スクリプトグループ
            feedback: 整合性チェックからのフィードバック
            
        Returns:
            再生成されたドキュメント
        """
        print(f"フィードバックに基づいてドキュメントを再生成します: {feedback}")
        
        # フィードバックを共通コンテキストとして追加
        for section in toc:
            section["context"] = f"{section['description']}\n\nフィードバック: {feedback}"
        
        # 更新した目次情報で再度セクションを生成
        new_sections = self._generate_sections(toc, groups)
        
        return {
            "table_of_contents": toc,
            "sections": new_sections
        }
        
    def _parse_toc_response(self, response):
        """
        LLMレスポンスから目次構造を抽出する処理
        
        Args:
            response: LLMからのレスポンステキスト
            
        Returns:
            目次構造のリスト
        """
        import json
        import re
        
        # JSONブロックを抽出
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        
        if json_match:
            json_str = json_match.group(1)
        else:
            # JSONブロックが見つからない場合は、レスポンス全体を試してみる
            json_str = response
        
        try:
            # 文字列からJSONをパース
            toc_items = json.loads(json_str)
            
            # 形式の検証
            if not isinstance(toc_items, list):
                raise ValueError("TOC should be a list")
                
            for item in toc_items:
                # 必須フィールドの確認
                if "title" not in item:
                    item["title"] = "無題のセクション"
                    
                if "description" not in item:
                    item["description"] = "説明なし"
                    
                if "script_ids" not in item:
                    item["script_ids"] = []
            
            return toc_items
            
        except json.JSONDecodeError as e:
            # JSONのパースに失敗した場合は、デフォルトの目次を返す
            print(f"目次のパースに失敗しました: {str(e)}")
            
            # フォールバック: シンプルな目次を作成
            return [
                {
                    "title": "システム概要",
                    "description": "システム全体の概要と主要コンポーネントの説明",
                    "script_ids": []
                },
                {
                    "title": "詳細分析",
                    "description": "システムの詳細な分析と実装の説明",
                    "script_ids": []
                }
            ] 