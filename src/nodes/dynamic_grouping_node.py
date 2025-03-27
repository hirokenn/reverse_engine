class DynamicGroupingNode:
    def __init__(self, llm_service):
        self.llm = llm_service
        
    def process(self, script_summaries):
        """
        スクリプト要約をグループ化し、各グループの説明を生成する
        
        Args:
            script_summaries: スクリプト要約のリスト（詳細な分析と簡潔な要約を含む）
            
        Returns:
            グループのリスト（各グループには説明が含まれる）
        """
        # スクリプトをグループ化するための分析（簡潔な要約のみを使用）
        groups = self._analyze_and_group(script_summaries)
        
        # 各グループの説明を生成（こちらでは詳細な分析を使用）
        for group in groups:
            group["description"] = self._generate_group_description(group, script_summaries)
            
        return groups
    
    def _analyze_and_group(self, script_summaries):
        """
        スクリプトの類似性に基づいてグループ化
        グルーピングには簡潔な要約のみを使用し、詳細な分析は使用しない
        
        Args:
            script_summaries: スクリプト要約のリスト
            
        Returns:
            グループのリスト
        """
        # プロンプトの作成
        prompt = "以下のスクリプト要約を機能や目的に基づいて論理的なグループに分けてください。\n\n"
        
        # グルーピングには簡潔な要約のみを使用
        for summary in script_summaries:
            # 簡潔な要約のみを抽出してグループ化に使用
            brief_summary = summary.get('summary', '')
            if not brief_summary and 'detailed_analysis' in summary:
                # 簡潔な要約がない場合は詳細からの最初の一文を使用（フォールバック）
                brief_summary = summary['detailed_analysis'].split('.')[0] + '.' if summary['detailed_analysis'] else ''
            
            prompt += f"ID: {summary['script_id']}\n要約: {brief_summary}\n\n"
            
        prompt += (
            "グループは次の形式でJSON形式で返してください：\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"group_id\": \"グループ1\",\n"
            "    \"name\": \"グループの名前\",\n"
            "    \"items\": [\n"
            "      {\"script_id\": \"ファイルパス\", \"reason\": \"このグループに含めた理由\"}\n"
            "    ]\n"
            "  }\n"
            "]\n"
            "```\n"
        )
        
        # プロンプトを表示
        print("\n===== グループ化 プロンプト =====")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("===== グループ化 プロンプト終了 =====\n")
        
        # LLMに問い合わせ
        response = self.llm.invoke(prompt)
        response_text = response.content
        
        # レスポンスからグループ情報を抽出
        groups = self._parse_grouping_response(response_text)
        return groups
    
    def _generate_group_description(self, group, script_summaries):
        """
        グループ内のスクリプト要約に基づいて説明を生成
        グループの説明生成には詳細な分析を使用する
        
        Args:
            group: スクリプトグループ
            script_summaries: スクリプト要約のリスト（詳細な分析を含む）
            
        Returns:
            グループの説明文
        """
        # グループに含まれるスクリプトのIDを取得
        group_script_ids = [item['script_id'] for item in group["items"]]
        
        # グループに含まれるスクリプトの詳細な分析を取得
        detailed_analyses = []
        for summary in script_summaries:
            if summary['script_id'] in group_script_ids and 'detailed_analysis' in summary:
                detailed_analyses.append({
                    'script_id': summary['script_id'],
                    'detailed_analysis': summary['detailed_analysis']
                })
        
        # グループ内のアイテムの情報を取得（理由と詳細な分析を含む）
        items_info = []
        for item in group["items"]:
            script_id = item['script_id']
            reason = item.get('reason', 'No reason provided')
            
            # 該当スクリプトの詳細な分析を見つける
            detailed_analysis = ""
            for analysis in detailed_analyses:
                if analysis['script_id'] == script_id:
                    detailed_analysis = analysis['detailed_analysis']
                    break
            
            items_info.append(f"- {script_id}: {reason}\n  詳細: {detailed_analysis[:200]}..." if len(detailed_analysis) > 200 else detailed_analysis)
        
        items_info_text = "\n".join(items_info)
        
        # プロンプトの作成
        prompt = f"""
        以下のスクリプトグループの説明を作成してください。
        このグループの役割や目的、含まれているスクリプトの共通点などを説明してください。
        
        グループ名: {group['name']}
        含まれるスクリプト:
        {items_info_text}
        
        説明は5-10行程度で、このグループのコードが全体のシステムの中でどのような役割を果たしているかを明確にしてください。
        """
        
        # プロンプトを表示
        print(f"\n===== グループ説明生成 プロンプト（{group['name']}）=====")
        print(prompt[:300] + "..." if len(prompt) > 300 else prompt)
        print("===== グループ説明生成 プロンプト終了 =====\n")
        
        # LLMに問い合わせ
        response = self.llm.invoke(prompt)
        return response.content.strip()
        
    def _parse_grouping_response(self, response):
        """
        LLMレスポンスからグループ情報を抽出する処理
        
        Args:
            response: LLMからのレスポンステキスト
            
        Returns:
            パースされたグループのリスト
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
            groups = json.loads(json_str)
            
            # グループの形式を検証
            if not isinstance(groups, list):
                raise ValueError("Groups should be a list")
                
            for group in groups:
                # 必須フィールドの確認
                if "group_id" not in group:
                    group["group_id"] = f"group_{groups.index(group) + 1}"
                
                if "name" not in group:
                    if "title" in group:
                        group["name"] = group["title"]
                    else:
                        group["name"] = f"Group {groups.index(group) + 1}"
                
                if "items" not in group or not isinstance(group["items"], list):
                    group["items"] = []
            
            return groups
            
        except json.JSONDecodeError as e:
            # JSONのパースに失敗した場合は、シンプルなグループを返す
            print(f"グループ情報のパースに失敗しました: {str(e)}")
            
            # フォールバック: すべてのスクリプトを1つのグループにまとめる
            return [
                {
                    "group_id": "default_group",
                    "name": "Default Group",
                    "items": []  # 空のリストを返す（呼び出し元で対処）
                }
            ] 