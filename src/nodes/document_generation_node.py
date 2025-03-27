from typing import Dict, List, Any
import json
import os
import uuid

from pydantic import BaseModel, Field
from src.model_types import GraphState, DocumentSection
from src.utils.file_utils import save_markdown, markdown_to_html
from src.utils.llm_utils import (
    get_llm,
    get_structured_llm,
    create_structured_prompt,
    DOCUMENT_GENERATION_SYSTEM_PROMPT,
    DOCUMENT_GENERATION_HUMAN_PROMPT
)
from src.utils.vector_store import VectorStoreManager


class DocumentContent(BaseModel):
    """ドキュメントコンテンツのスキーマ"""
    content: str = Field(description="生成されたドキュメントのコンテンツ（Markdown形式）")


def generate_document_sections(state: GraphState, vector_store_manager: VectorStoreManager = None) -> GraphState:
    """
    グループごとにドキュメントセクションを生成するノード
    
    Args:
        state: グラフの現在の状態
        vector_store_manager: ベクトルストアマネージャ（オプション）
    
    Returns:
        更新されたグラフ状態
    """
    if state.status != "grouping_complete":
        # グループ化が完了していない場合はスキップ
        return state
    
    print("ドキュメントセクションの生成を開始します...")
    
    # ドキュメントセクションの初期化
    if not state.document_sections:
        state.document_sections = {}
    
    # 各グループについてドキュメントセクションを生成
    order = 1
    
    # 1. システム概要セクション
    system_overview_id = f"section_overview_{str(uuid.uuid4())[:8]}"
    overview_content = _generate_system_overview(state, vector_store_manager)
    overview_section = DocumentSection(
        section_id=system_overview_id,
        title="システム概要",
        content=overview_content,
        group_id="system_overview",
        order=order
    )
    state.document_sections[system_overview_id] = overview_section
    _save_document_section(overview_section)
    order += 1
    
    # 2. 各グループのセクション
    for group_id, group in state.groups.items():
        # セクションIDを生成
        section_id = f"section_{str(uuid.uuid4())[:8]}"
        
        # ドキュメントセクションを生成
        section_content = _generate_section_for_group(state, group_id, vector_store_manager)
        
        # ドキュメントセクションを状態に追加
        section = DocumentSection(
            section_id=section_id,
            title=f"{group.group_name}",
            content=section_content,
            group_id=group_id,
            order=order
        )
        
        state.document_sections[section_id] = section
        
        # Markdownファイルとして保存
        _save_document_section(section)
        
        order += 1
    
    # 3. インターフェースセクション
    interface_id = f"section_interface_{str(uuid.uuid4())[:8]}"
    interface_content = _generate_interfaces_section(state, vector_store_manager)
    interface_section = DocumentSection(
        section_id=interface_id,
        title="システム間インターフェース",
        content=interface_content,
        group_id="system_interfaces",
        order=order
    )
    state.document_sections[interface_id] = interface_section
    _save_document_section(interface_section)
    order += 1
    
    # 4. 全体的なビジネスロジックとデータフロー
    logic_id = f"section_logic_{str(uuid.uuid4())[:8]}"
    logic_content = _generate_business_logic_section(state, vector_store_manager)
    logic_section = DocumentSection(
        section_id=logic_id,
        title="ビジネスロジックとデータフロー",
        content=logic_content,
        group_id="business_logic",
        order=order
    )
    state.document_sections[logic_id] = logic_section
    _save_document_section(logic_section)
    
    state.status = "document_generation_complete"
    
    return state


def _generate_system_overview(state: GraphState, vector_store_manager: VectorStoreManager = None) -> str:
    """
    システム全体の概要セクションを生成
    
    Args:
        state: グラフの現在の状態
        vector_store_manager: ベクトルストアマネージャ
    
    Returns:
        生成されたセクションコンテンツ
    """
    # 全てのグループの概要を集約
    groups_summary = []
    for group_id, group in state.groups.items():
        if group.summary:
            groups_summary.append(f"**{group.group_name}**: {group.summary}")
    
    groups_summary_text = "\n\n".join(groups_summary)
    
    # 全てのファイルタイプを集計
    file_types = {}
    for result in state.analysis_results.values():
        file_type = result.file_type
        if file_type in file_types:
            file_types[file_type] += 1
        else:
            file_types[file_type] = 1
    
    file_types_text = "\n".join([f"- {file_type}: {count}ファイル" for file_type, count in file_types.items()])
    
    # RAGを使用してシステム全体のコンテキストを取得
    rag_context = ""
    if vector_store_manager:
        # システム全体に関するクエリでRAG検索
        search_query = "システム全体のアーキテクチャと主要コンポーネントの関係"
        similar_docs = vector_store_manager.search_similar_files(search_query, k=5)
        
        if similar_docs:
            rag_context = "\n\n## 関連コンテキスト:\n"
            for doc in similar_docs:
                rag_context += f"\n---\n{doc['content']}\n---\n"
    
    # 構造化出力用のLLMを取得
    structured_llm = get_structured_llm(DocumentContent)
    
    # プロンプトを作成
    prompt_template = f"""
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
以下の情報を元に、システム全体の概要セクションを作成してください。

## 分析されたグループ情報:
{groups_summary_text}

## ファイルタイプの分布:
{file_types_text}

{rag_context}

以下の内容を含む、システム全体の概要セクションをMarkdown形式で生成してください:
1. システムの目的と概要
2. 主要コンポーネントの説明
3. 全体アーキテクチャの概要
4. 技術スタックの特徴
5. システム間の主要な依存関係

技術的に正確で詳細な説明を心がけてください。
"""
    
    # プロンプトを表示
    print("\n===== システム概要生成 プロンプト =====")
    print(prompt_template[:500] + "..." if len(prompt_template) > 500 else prompt_template)
    print("===== システム概要生成 プロンプト終了 =====\n")
    
    # 構造化出力でLLMを呼び出し
    response = structured_llm.invoke(prompt_template)
    
    return response.content


def _generate_section_for_group(
    state: GraphState, 
    group_id: str,
    vector_store_manager: VectorStoreManager = None
) -> str:
    """
    グループに対してドキュメントセクションを生成
    
    Args:
        state: グラフの現在の状態
        group_id: グループID
        vector_store_manager: ベクトルストアマネージャ（オプション）
    
    Returns:
        生成されたセクションコンテンツ
    """
    group = state.groups.get(group_id)
    
    if not group:
        return "グループ情報が見つかりません。"
    
    # グループに含まれるファイルの解析結果を集約
    group_files_info = []
    
    for file_path in group.files:
        if file_path in state.analysis_results:
            result = state.analysis_results[file_path]
            file_info = {
                "file_path": file_path,
                "summary": result.summary,
                "purpose": result.purpose,
                "functions": result.functions,
                "dependencies": result.dependencies,
                "data_structures": result.data_structures,
                "business_rules": result.business_rules,
                "technical_debt": result.technical_debt
            }
            group_files_info.append(file_info)
    
    # グループファイル情報をJSON文字列に変換
    group_files_json = json.dumps(group_files_info, ensure_ascii=False, indent=2)
    
    # このセクション固有のクエリを作成
    section_specific_query = f"{group.group_name} {group.description}"
    
    # RAGを使用して関連コンテキストを取得
    rag_context = ""
    if vector_store_manager:
        # セクション固有のクエリでRAG検索
        similar_docs = vector_store_manager.search_similar_files(section_specific_query, k=3)
        
        if similar_docs:
            rag_context = "\n\n## 関連コンテキスト:\n"
            for doc in similar_docs:
                # 既にこのグループに含まれているファイル以外の情報を追加
                if not any(doc['metadata'].get('file_path', '') in file_info['file_path'] for file_info in group_files_info):
                    rag_context += f"\n---\n{doc['content']}\n---\n"
    
    # 構造化出力用のLLMを取得
    structured_llm = get_structured_llm(DocumentContent)
    
    # プロンプトを作成
    prompt = f"""
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
以下のグループに関する解析情報から、仕様書のセクションを作成してください：

グループ名: {group.group_name}
グループ説明: {group.description}

このグループに含まれるファイル:
{group_files_json}

{rag_context}

Markdown形式で、詳細な仕様書セクションを作成してください。
タイトルは適切なものを選び、必要に応じてサブセクションを追加してください。
このセクションはシステム全体の仕様書の一部となります。
"""
    
    # プロンプトを表示
    print(f"\n===== グループセクション生成 プロンプト（{group.group_name}）=====")
    print(f"グループ名: {group.group_name}, グループ説明: {group.description[:50]}...")
    print(f"ファイル情報: {len(group_files_info)}ファイル, RAGコンテキスト長: {len(rag_context)}")
    print("===== グループセクション生成 プロンプト終了 =====\n")
    
    # 構造化出力でLLMを呼び出し
    response = structured_llm.invoke(prompt)
    
    return response.content


def _generate_interfaces_section(state: GraphState, vector_store_manager: VectorStoreManager = None) -> str:
    """
    システム間インターフェースのセクションを生成
    
    Args:
        state: グラフの現在の状態
        vector_store_manager: ベクトルストアマネージャ
    
    Returns:
        生成されたセクションコンテンツ
    """
    # 全ての依存関係を抽出
    all_dependencies = []
    for result in state.analysis_results.values():
        all_dependencies.extend(result.dependencies)
    
    # 重複を削除
    unique_dependencies = list(set(all_dependencies))
    dependencies_text = "\n".join([f"- {dep}" for dep in unique_dependencies])
    
    # RAGを使用してインターフェースに関する情報を取得
    rag_context = ""
    if vector_store_manager:
        search_query = "システム間インターフェース 外部連携 API 依存関係"
        similar_docs = vector_store_manager.search_similar_files(search_query, k=3)
        
        if similar_docs:
            rag_context = "\n\n## 関連コンテキスト:\n"
            for doc in similar_docs:
                rag_context += f"\n---\n{doc['content']}\n---\n"
    
    # 構造化出力用のLLMを取得
    structured_llm = get_structured_llm(DocumentContent)
    
    # プロンプトを作成
    prompt_template = f"""
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
以下の情報を元に、システム間インターフェースのセクションを作成してください。

## 検出された依存関係:
{dependencies_text}

{rag_context}

以下の内容を含む、システム間インターフェースのセクションをMarkdown形式で生成してください:
1. 外部システムとの連携概要
2. 主要なAPIや通信インターフェース
3. データ交換フォーマット
4. インターフェースの制約や前提条件
5. エラーハンドリングの方針

技術的に正確で詳細な説明を心がけてください。
"""
    
    # 構造化出力でLLMを呼び出し
    response = structured_llm.invoke(prompt_template)
    
    return response.content


def _generate_business_logic_section(state: GraphState, vector_store_manager: VectorStoreManager = None) -> str:
    """
    ビジネスロジックとデータフローのセクションを生成
    
    Args:
        state: グラフの現在の状態
        vector_store_manager: ベクトルストアマネージャ
    
    Returns:
        生成されたセクションコンテンツ
    """
    # 全てのビジネスルールを抽出
    all_business_rules = []
    for result in state.analysis_results.values():
        all_business_rules.extend(result.business_rules)
    
    # 重複を削除
    unique_rules = list(set(all_business_rules))
    rules_text = "\n".join([f"- {rule}" for rule in unique_rules])
    
    # 全てのデータ構造を抽出
    all_data_structures = []
    for result in state.analysis_results.values():
        all_data_structures.extend(result.data_structures)
    
    # RAGを使用してビジネスロジックに関する情報を取得
    rag_context = ""
    if vector_store_manager:
        search_query = "ビジネスロジック データフロー 処理ルール"
        similar_docs = vector_store_manager.search_similar_files(search_query, k=4)
        
        if similar_docs:
            rag_context = "\n\n## 関連コンテキスト:\n"
            for doc in similar_docs:
                rag_context += f"\n---\n{doc['content']}\n---\n"
    
    # 構造化出力用のLLMを取得
    structured_llm = get_structured_llm(DocumentContent)
    
    # プロンプトを作成
    prompt_template = f"""
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
以下の情報を元に、ビジネスロジックとデータフローのセクションを作成してください。

## 検出されたビジネスルール:
{rules_text}

## データ構造情報:
{json.dumps(all_data_structures, ensure_ascii=False, indent=2)}

{rag_context}

以下の内容を含む、ビジネスロジックとデータフローのセクションをMarkdown形式で生成してください:
1. 主要なビジネスフロー
2. 重要なビジネスルールの説明
3. データの流れと変換プロセス
4. 主要なデータ構造とその関係
5. ビジネスロジックの制約条件

技術的に正確で詳細な説明を心がけてください。
"""
    
    # 構造化出力でLLMを呼び出し
    response = structured_llm.invoke(prompt_template)
    
    return response.content


def _save_document_section(section: DocumentSection, output_dir: str = "./output/sections") -> None:
    """
    ドキュメントセクションをMarkdownファイルとして保存
    
    Args:
        section: ドキュメントセクション
        output_dir: 出力ディレクトリ
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Markdownファイルとして保存
    md_file_path = os.path.join(output_dir, f"{section.section_id}.md")
    save_markdown(section.content, md_file_path)
    
    # HTMLファイルとしても保存
    html_file_path = os.path.join(output_dir, f"{section.section_id}.html")
    markdown_to_html(section.content, html_file_path)
    
    # メタデータをJSONとして保存
    meta_file_path = os.path.join(output_dir, f"{section.section_id}.meta.json")
    with open(meta_file_path, 'w', encoding='utf-8') as f:
        json.dump(section.model_dump(), f, ensure_ascii=False, indent=2) 