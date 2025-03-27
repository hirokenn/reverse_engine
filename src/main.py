import os
import argparse
import time
from typing import Dict, List, Any

from langgraph.graph import StateGraph, END

from src.model_types import GraphState
from src.nodes.script_analysis_node import ScriptAnalysisNode
from src.nodes.dynamic_grouping_node import DynamicGroupingNode
from src.nodes.document_orchestration_node import DocumentOrchestrationNode
from src.nodes.document_generation_node import generate_document_sections
from src.nodes.consistency_check_node import check_consistency
from src.utils.config import load_config
from src.utils.file_utils import get_file_list, markdown_to_pdf
from src.utils.vector_store import VectorStoreManager

def text_extraction_node(state: GraphState) -> GraphState:
    """
    ソースコードのスクリプトごとにテキスト化するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # 現在の進行状況を確認
    if state.current_file_index >= state.total_files:
        # すべてのファイルの処理が完了
        state.status = "text_extraction_complete"
        return state
    
    # 処理対象のファイルリストから現在のファイルパスを取得
    file_paths = list(state.source_files.keys())
    current_file_path = file_paths[state.current_file_index]
    
    print(f"ファイル読み込み中 ({state.current_file_index + 1}/{state.total_files}): {current_file_path}")
    
    # 次のファイルのインデックスに進む
    state.current_file_index += 1
    
    return state

def process_script_analysis(state: GraphState) -> GraphState:
    """
    スクリプト解析を実行するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # テキスト化が完了していない場合はスキップ
    if state.status != "text_extraction_complete":
        return state
    
    print("スクリプト解析を開始します...")
    
    # ScriptAnalysisNodeを使用して全てのスクリプトを解析
    script_analysis_node = ScriptAnalysisNode(state.vector_store)
    
    # ソースファイルをスクリプト解析用の形式に変換
    scripts = []
    for file_path, source_file in state.source_files.items():
        scripts.append({
            "file_path": file_path,
            "content": source_file.content,
            "file_type": source_file.file_type
        })
    
    # スクリプト解析を実行
    analysis_results = script_analysis_node.process(scripts)
    
    # 解析結果を状態に追加
    for result in analysis_results:
        state.analysis_results[result["script_id"]] = result
    
    state.status = "script_analysis_complete"
    return state

def process_dynamic_grouping(state: GraphState) -> GraphState:
    """
    動的なグループ化を実行するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # スクリプト解析が完了していない場合はスキップ
    if state.status != "script_analysis_complete":
        return state
    
    print("スクリプトのグループ化を実行中...")
    
    # LLMサービスを取得
    from src.utils.llm_utils import get_llm
    llm_service = get_llm()
    
    # DynamicGroupingNodeを初期化
    dynamic_grouping_node = DynamicGroupingNode(llm_service)
    
    # スクリプト要約をリスト形式に変換
    script_summaries = []
    for script_id, result in state.analysis_results.items():
        script_summaries.append({
            "script_id": script_id,
            "summary": result.summary if hasattr(result, "summary") else "",
            "detailed_analysis": result.detailed_analysis if hasattr(result, "detailed_analysis") else "",
            "content": result.content if hasattr(result, "content") else ""
        })
    
    # グループ化を実行
    groups = dynamic_grouping_node.process(script_summaries)
    
    # グループ情報を状態に追加
    for group in groups:
        group_id = group["group_id"]
        state.groups[group_id] = {
            "group_id": group_id,
            "group_name": group["name"],
            "description": group["description"],
            "files": [item["script_id"] for item in group["items"]],
            "summary": group.get("summary", None)
        }
    
    state.status = "grouping_complete"
    return state

def process_document_orchestration(state: GraphState) -> GraphState:
    """
    ドキュメント構造を生成するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # グループ化が完了していない場合は処理をスキップ
    if state.status != "grouping_complete" and state.status != "document_regeneration_required":
        return state
    
    print("ドキュメント構造を生成中...")
    
    # LLMサービスを取得
    from src.utils.llm_utils import get_llm
    llm_service = get_llm()
    
    # RAGシステムを初期化
    from src.rag_system import RAGSystem
    rag_system = RAGSystem(vector_store=state.vector_store, llm=llm_service)
    
    # DocumentOrchestrationNodeを初期化
    document_orchestration_node = DocumentOrchestrationNode(llm_service, rag_system)
    
    # グループ情報をリスト形式に変換
    groups = []
    for group_id, group in state.groups.items():
        groups.append({
            "group_id": group_id,
            "name": group.group_name,
            "description": group.description,
            "items": [{"script_id": file_path} for file_path in group.files]
        })
    
    # ドキュメント構造を生成
    document = document_orchestration_node.process(groups)
    
    # ドキュメント構造を状態に追加
    state.document_outline = {
        "title": "システム仕様書",
        "introduction": "自動生成されたシステム仕様書",
        "sections": document["table_of_contents"],
        "appendices": []
    }
    
    state.status = "document_orchestration_complete"
    return state

def process_document_generation(state: GraphState) -> GraphState:
    """
    ドキュメントセクションを生成するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # ドキュメント構造が完了していない場合は処理をスキップ
    if state.status != "document_orchestration_complete" and state.status != "document_regeneration_required":
        return state
    
    print("ドキュメントセクションを生成中...")
    
    # DocumentGenerationNodeを使用してセクションを生成
    state = generate_document_sections(state, state.vector_store)
    
    state.status = "document_generation_complete"
    return state

def process_consistency_check(state: GraphState) -> GraphState:
    """
    ドキュメントの整合性をチェックするノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # ドキュメント生成が完了していない場合は処理をスキップ
    if state.status != "document_generation_complete":
        return state
    
    print("ドキュメントの整合性をチェック中...")
    
    # ConsistencyCheckNodeを使用して整合性をチェック
    state = check_consistency(state)
    
    # 整合性チェック結果を評価
    all_consistent = all(
        result.is_consistent for result in state.consistency_checks.values()
    )
    
    if not all_consistent:
        # 整合性に問題がある場合は再生成が必要
        state.status = "document_regeneration_required"
        return state
    
    # 整合性に問題がなければ完了
    state.status = "consistency_check_complete"
    return state

def export_to_pdf(state: GraphState) -> GraphState:
    """
    最終ドキュメントをPDFに出力するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # 整合性チェックが完了していない場合は処理をスキップ
    if state.status != "consistency_check_complete":
        return state
    
    print("ドキュメントをPDFとして出力中...")
    
    # 出力ディレクトリを作成
    output_dir = "./output/final"
    os.makedirs(output_dir, exist_ok=True)
    
    # 目次を作成
    toc_path = os.path.join(output_dir, "table_of_contents.md")
    with open(toc_path, "w", encoding="utf-8") as f:
        f.write(f"# {state.document_outline.title}\n\n")
        f.write(f"{state.document_outline.introduction}\n\n")
        f.write("## 目次\n\n")
        
        for i, section in enumerate(state.document_outline.sections):
            f.write(f"{i+1}. {section['title']} - {section['description']}\n")
    
    # 各セクションのMarkdownファイルを作成
    all_sections_markdown = []
    all_sections_markdown.append(toc_path)
    
    for section_id, section in state.document_sections.items():
        section_path = os.path.join(output_dir, f"section_{section.order}_{section.title.replace(' ', '_')}.md")
        with open(section_path, "w", encoding="utf-8") as f:
            f.write(f"# {section.title}\n\n")
            f.write(section.content)
        all_sections_markdown.append(section_path)
    
    # すべてのMarkdownファイルを結合してPDFに変換
    pdf_path = os.path.join(output_dir, "system_documentation.pdf")
    markdown_to_pdf(all_sections_markdown, pdf_path)
    
    print(f"ドキュメントが正常に生成されました: {pdf_path}")
    
    state.status = "completed"
    state.is_complete = True
    return state

def parse_arguments():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description="レガシーシステムリバースエンジニアリングAI")
    
    parser.add_argument(
        "--code-path",
        type=str,
        help="解析対象のコードパス（ディレクトリまたはファイル）"
    )
    
    parser.add_argument(
        "--extensions",
        type=str,
        nargs="+",
        help="解析対象のファイル拡張子（例: .py .js .java）"
    )
    
    return parser.parse_args()

def create_workflow(initial_state: GraphState):
    """ワークフロー（状態遷移グラフ）を作成する"""
    # StateGraphを作成
    workflow = StateGraph(GraphState)
    
    # ノードを追加
    workflow.add_node("text_extraction", text_extraction_node)
    workflow.add_node("script_analysis", process_script_analysis)
    workflow.add_node("dynamic_grouping", process_dynamic_grouping)
    workflow.add_node("document_orchestration", process_document_orchestration)
    workflow.add_node("document_generation", process_document_generation)
    workflow.add_node("consistency_check", process_consistency_check)
    workflow.add_node("export_to_pdf", export_to_pdf)
    
    # エッジを定義
    # text_extractionノードが完了するまで繰り返し実行
    workflow.add_conditional_edges(
        "text_extraction",
        lambda state: "script_analysis" if state.status == "text_extraction_complete" else "text_extraction"
    )
    
    # script_analysisノードからdynamic_groupingノードへ
    workflow.add_edge("script_analysis", "dynamic_grouping")
    
    # dynamic_groupingノードからdocument_orchestrationノードへ
    workflow.add_edge("dynamic_grouping", "document_orchestration")
    
    # document_orchestrationノードからdocument_generationノードへ
    workflow.add_edge("document_orchestration", "document_generation")
    
    # document_generationノードからconsistency_checkノードへ
    workflow.add_edge("document_generation", "consistency_check")
    
    # consistency_checkノードから条件分岐
    workflow.add_conditional_edges(
        "consistency_check",
        lambda state: "document_orchestration" if state.status == "document_regeneration_required" else "export_to_pdf"
    )
    
    # export_to_pdfノードから終了
    workflow.add_edge("export_to_pdf", END)

    workflow.set_entry_point("text_extraction")
    
    # グラフをコンパイル
    return workflow.compile()

def main():
    """メイン処理"""
    start_time = time.time()
    
    # コマンドライン引数を解析
    args = parse_arguments()
    
    # 設定を読み込む
    config = load_config()
    
    # 解析対象のコードパスを決定
    code_path = args.code_path or config["legacy_code_path"]
    
    # 解析対象のファイルリストを取得
    if os.path.isfile(code_path):
        # 単一ファイルの場合
        code_paths = [code_path]
    else:
        # ディレクトリの場合
        extensions = args.extensions if args.extensions else config.get("file_extensions", [".py", ".js", ".java"])
        code_paths = get_file_list(code_path, extensions=extensions)
    
    if not code_paths:
        print(f"解析対象のファイルが見つかりません: {code_path}")
        return
    
    print("=== ソースコード リバースエンジニアリング AI ===")
    print(f"対象パス: {code_path}")
    print(f"ファイル数: {len(code_paths)}")
    
    # ベクトルストアを初期化
    vector_store = VectorStoreManager(
        persist_directory=config["chroma_db_path"],
        collection_name="source_code_analysis"
    )
    
    # ソースファイルを準備
    source_files = {}
    for path in code_paths:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            source_files[path] = {
                "file_path": path,
                "content": content,
                "file_type": os.path.splitext(path)[1]
            }
        except Exception as e:
            print(f"ファイル {path} の読み込み中にエラーが発生しました: {str(e)}")
    
    # 初期状態を作成
    from src.model_types import SourceFile
    
    initial_state = GraphState(
        source_files={path: SourceFile(file_path=path, content=data["content"], file_type=data["file_type"]) for path, data in source_files.items()},
        current_file_index=0,
        total_files=len(source_files),
        vector_store=vector_store,
        status="initialized"
    )
    
    # ワークフローを作成して実行
    app = create_workflow(initial_state)
    
    # グラフを実行
    try:
        for state in app.stream(initial_state):
            current_status = state["status"] if "status" in state else "unknown"
            
            if current_status == "text_extraction_complete":
                print("テキスト化が完了しました。スクリプト解析を開始します...")
                
            elif current_status == "script_analysis_complete":
                print("スクリプト解析が完了しました。グループ化を開始します...")
                
            elif current_status == "grouping_complete":
                print("グループ化が完了しました。ドキュメント構造の生成を開始します...")
                
            elif current_status == "document_orchestration_complete":
                print("ドキュメント構造が完了しました。セクション生成を開始します...")
                
            elif current_status == "document_generation_complete":
                print("ドキュメントセクションが生成されました。整合性チェックを開始します...")
                
            elif current_status == "document_regeneration_required":
                print("整合性に問題があります。ドキュメントを再生成します...")
                
            elif current_status == "consistency_check_complete":
                print("整合性チェックが完了しました。PDFを出力します...")
                
            elif current_status == "completed":
                elapsed_time = time.time() - start_time
                print(f"処理が完了しました。所要時間: {elapsed_time:.2f}秒")
    
    except Exception as e:
        print(f"処理中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 