from typing import List, Dict, Any, Optional
import os

class RAGSystem:
    """
    RAG (Retrieval Augmented Generation) システム
    
    ベクトルストアを使用して関連文書を検索し、LLMでコンテンツを生成するシステム
    """
    
    def __init__(self, vector_store, llm):
        """
        RAGシステムを初期化
        
        Args:
            vector_store: ベクトルストア
            llm: 言語モデル
        """
        self.vector_store = vector_store
        self.llm = llm
    
    def search_similar_documents(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        クエリに関連する文書を検索
        
        Args:
            query: 検索クエリ
            k: 取得する文書数
            
        Returns:
            関連文書のリスト
        """
        if self.vector_store is None:
            return []
            
        return self.vector_store.search_similar_files(query, k=k)
    
    def generate_content(self, query: str, context: str, document_ids: List[str] = None) -> str:
        """
        RAGシステムを使用してコンテンツを生成
        
        Args:
            query: 生成するコンテンツのクエリ/タイトル
            context: 追加コンテキスト情報
            document_ids: 参照すべき文書ID（ファイルパスなど）のリスト
            
        Returns:
            生成されたコンテンツ
        """
        # RAGコンテキストを取得
        rag_context = self._get_rag_context(query, document_ids)
        
        # プロンプトを作成
        prompt = self._create_generation_prompt(query, context, rag_context)
        
        # プロンプトを表示
        print("\n===== RAGシステム プロンプト =====")
        print(f"クエリ: {query}")
        print(f"コンテキスト: {context}")
        print("システムメッセージ:", prompt[0]["content"])
        print("ユーザーメッセージ:", prompt[1]["content"][:300] + "..." if len(prompt[1]["content"]) > 300 else prompt[1]["content"])
        print("===== RAGシステム プロンプト終了 =====\n")
        
        # LLMを使用してコンテンツを生成
        response = self.llm.invoke(prompt)
        
        return response.content
    
    def _get_rag_context(self, query: str, document_ids: List[str] = None) -> str:
        """
        RAGコンテキストを取得
        
        Args:
            query: 検索クエリ
            document_ids: 特定の文書ID
            
        Returns:
            RAGコンテキスト
        """
        # ベクトルストアが設定されていない場合は空の文字列を返す
        if self.vector_store is None:
            return ""
        
        # クエリを拡張
        enhanced_query = f"{query} 詳細 実装"
        
        # 関連文書を検索
        similar_docs = self.search_similar_documents(enhanced_query, k=3)
        
        if not similar_docs:
            return ""
        
        # RAGコンテキストを作成
        rag_context = "\n\n## 関連コンテキスト:\n"
        for doc in similar_docs:
            rag_context += f"\n---\n{doc['content']}\n---\n"
        
        return rag_context
    
    def _create_generation_prompt(self, query: str, context: str, rag_context: str) -> str:
        """
        生成用プロンプトを作成
        
        Args:
            query: 生成するコンテンツのクエリ/タイトル
            context: 追加コンテキスト情報
            rag_context: RAGシステムから取得したコンテキスト
            
        Returns:
            生成用プロンプト
        """
        system_message = """
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
与えられた情報から、技術的に正確で詳細な文書を作成してください。
"""
        
        human_message = f"""
## セクションタイトル:
{query}

## セクションの概要/説明:
{context}

{rag_context}

以下の内容を含む、詳細なセクションをMarkdown形式で生成してください:
1. 概要と目的
2. 主要な機能と特徴
3. アーキテクチャと設計
4. 実装の詳細
5. 制約と前提条件

技術的に正確で詳細な説明を心がけてください。
"""
        
        return [{"role": "system", "content": system_message}, {"role": "user", "content": human_message}] 