"""
モデルの型定義を行うモジュール
このモジュールはアプリケーション全体で使用されるデータモデルを定義します。
Pydanticを使用して型安全なモデル定義と検証を実現しています。
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from src.utils.vector_store import VectorStoreManager


class ConsistencyCheckFeedback(BaseModel):
    """
    整合性チェックのフィードバック詳細を表すモデル
    
    特定の評価領域（技術的正確性、完全性など）における整合性評価の
    詳細情報を格納します。
    """
    area: str  # フィードバック対象領域（technical_accuracy, completeness, など）
    is_consistent: bool  # この領域での整合性
    score: float  # 整合性スコア（0.0-1.0）
    reason: str  # 整合性の判断理由
    suggestions: List[str] = Field(default_factory=list)  # 改善提案


class ConsistencyCheckResult(BaseModel):
    """
    整合性チェック結果を表すモデル
    
    ドキュメントセクションの整合性チェック結果を格納します。
    詳細なフィードバックや否定回数などの情報も含みます。
    """
    section_id: str  # 対象セクションID
    is_consistent: bool  # 整合性の判断結果
    feedback: Optional[str] = None  # 全体的なフィードバックメッセージ
    rejection_count: int = 0  # 否定された回数
    detailed_feedback: List[ConsistencyCheckFeedback] = Field(default_factory=list)  # 詳細なフィードバック
    overall_score: float = 1.0  # 全体的な整合性スコア（0.0-1.0）


class SourceFile(BaseModel):
    """
    ソースファイルの情報を表すモデル
    
    解析対象のソースファイルの基本情報を格納します。
    """
    file_path: str  # ファイルパス
    content: str  # ファイル内容
    file_type: str  # ファイルの種類（Python, JavaScript, etc.）


class FileAnalysisResult(BaseModel):
    """
    ファイル解析結果を表すモデル
    
    ソースファイルの解析結果を格納します。
    ファイルの目的、関数、依存関係などの情報が含まれます。
    """
    file_path: str  # 解析対象ファイルのパス
    file_type: str  # ファイルの種類
    summary: str  # ファイルの概要
    purpose: str  # ファイルの目的
    functions: List[Dict[str, Any]] = Field(default_factory=list)  # ファイル内の関数情報
    dependencies: List[str] = Field(default_factory=list)  # 依存関係
    data_structures: List[Dict[str, Any]] = Field(default_factory=list)  # データ構造
    business_rules: List[str] = Field(default_factory=list)  # ビジネスルール
    technical_debt: List[str] = Field(default_factory=list)  # 技術的負債


class GroupInfo(BaseModel):
    """
    ファイルグループの情報を表すモデル
    
    関連するソースファイルをグループ化した情報を格納します。
    """
    group_id: str  # グループID
    group_name: str  # グループ名
    description: str  # グループの説明
    files: List[str] = Field(default_factory=list)  # 所属するファイルパスのリスト
    summary: Optional[str] = None  # グループの要約


class DocumentSection(BaseModel):
    """
    ドキュメントのセクションを表すモデル
    
    生成されたドキュメントの各セクション情報を格納します。
    """
    section_id: str  # セクションID
    title: str  # セクションタイトル
    content: str  # セクション内容
    group_id: str  # 所属するグループID
    order: int  # セクションの順序


class DocumentOutline(BaseModel):
    """
    ドキュメントの全体構成を表すモデル
    
    生成されたドキュメントの目次や構成情報を格納します。
    """
    title: str  # ドキュメントのタイトル
    introduction: str  # 導入部
    sections: List[Dict[str, Any]] = Field(default_factory=list)  # セクション定義
    appendices: List[Dict[str, Any]] = Field(default_factory=list)  # 付録定義


class GraphState(BaseModel):
    """
    グラフの状態を表すモデル
    
    ワークフローのステップ間で引き継がれる状態情報を格納します。
    アプリケーション全体の状態管理に使用されます。
    """
    # 任意の型を許可（VectorStoreManagerなどの外部クラスをサポート）
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    source_files: Dict[str, SourceFile] = Field(default_factory=dict)  # 解析対象のソースファイル
    analysis_results: Dict[str, FileAnalysisResult] = Field(default_factory=dict)  # ファイル解析結果
    groups: Dict[str, GroupInfo] = Field(default_factory=dict)  # ファイルグループ情報
    document_sections: Dict[str, DocumentSection] = Field(default_factory=dict)  # ドキュメントセクション
    consistency_checks: Dict[str, ConsistencyCheckResult] = Field(default_factory=dict)  # 整合性チェック結果
    document_outline: Optional[DocumentOutline] = None  # ドキュメント構成
    vector_store: Optional[VectorStoreManager] = None  # ベクトルストアマネージャー
    current_file_index: int = 0  # 現在処理中のファイルインデックス
    total_files: int = 0  # 処理対象ファイルの総数
    status: str = "initialized"  # 現在の状態
    is_complete: bool = False  # 処理完了フラグ
    user_input: Optional[str] = None  # ユーザー入力 