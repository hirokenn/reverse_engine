from typing import List, Dict, Any, Optional
import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import uuid


class VectorStoreManager:
    """ベクトルストアを管理するクラス"""
    
    def __init__(self, persist_directory: str, collection_name: str = "legacy_code_analysis"):
        """
        初期化
        
        Args:
            persist_directory: ベクトルストアの永続化ディレクトリ
            collection_name: コレクション名
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        os.makedirs(persist_directory, exist_ok=True)
        
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embeddings,
            collection_name=collection_name
        )
    
    def add_analysis_results(self, analysis_results: List[Dict[str, Any]]) -> None:
        """
        解析結果をベクトルストアに追加
        
        Args:
            analysis_results: 解析結果のリスト
        """
        documents = []
        metadatas = []
        ids = []
        
        for result in analysis_results:
            doc_id = str(uuid.uuid4())
            
            # ドキュメントの内容
            content = f"""
ファイルパス: {result['file_path']}
ファイルタイプ: {result['file_type']}
要約: {result['summary']}
目的: {result['purpose']}

# 機能
{self._format_list_items(result.get('functions', []))}

# 依存関係
{self._format_list_items(result.get('dependencies', []))}

# データ構造
{self._format_list_items(result.get('data_structures', []))}

# ビジネスルール
{self._format_list_items(result.get('business_rules', []))}
            """
            
            document = Document(
                page_content=content,
                metadata={
                    "file_path": result["file_path"],
                    "file_type": result["file_type"],
                    "doc_id": doc_id
                }
            )
            
            documents.append(document)
            metadatas.append(document.metadata)
            ids.append(doc_id)
        
        if documents:
            self.vector_store.add_documents(documents=documents)
    
    def search_similar_files(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        クエリに似た文書を検索
        
        Args:
            query: 検索クエリ
            k: 取得する結果の数
            
        Returns:
            類似ドキュメントのリスト
        """
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score
            }
            for doc, score in results
        ]
    
    def get_all_documents(self) -> List[Document]:
        """
        すべてのドキュメントを取得
        
        Returns:
            ドキュメントのリスト
        """
        return self.vector_store.get()
    
    def _format_list_items(self, items: List[Any]) -> str:
        """リスト項目をフォーマット"""
        if not items:
            return "なし"
        
        if isinstance(items[0], dict):
            return "\n".join([f"- {self._dict_to_str(item)}" for item in items])
        else:
            return "\n".join([f"- {item}" for item in items])
    
    def _dict_to_str(self, d: Dict[str, Any]) -> str:
        """辞書を文字列に変換"""
        return ", ".join([f"{k}: {v}" for k, v in d.items()]) 