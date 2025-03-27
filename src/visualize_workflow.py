from graphviz import Digraph
from langgraph.graph import StateGraph, START, END
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class MockGraphState:
    """モック用の簡易的なGraphState"""
    status: str = "initialized"

def create_mock_workflow():
    """モックのワークフローを作成"""
    workflow = StateGraph(MockGraphState)
    
    # ノードを追加
    workflow.add_node("text_extraction", lambda x: x)
    workflow.add_node("script_analysis", lambda x: x)
    workflow.add_node("dynamic_grouping", lambda x: x)
    workflow.add_node("document_orchestration", lambda x: x)
    workflow.add_node("document_generation", lambda x: x)
    workflow.add_node("consistency_check", lambda x: x)
    workflow.add_node("export_to_pdf", lambda x: x)
    
    # 開始ノードを追加
    workflow.add_edge(START, "text_extraction")
    
    # エッジを定義
    workflow.add_conditional_edges(
        "text_extraction",
        lambda state: "script_analysis" if state.status == "text_extraction_complete" else "text_extraction"
    )
    
    workflow.add_edge("script_analysis", "dynamic_grouping")
    workflow.add_edge("dynamic_grouping", "document_orchestration")
    workflow.add_edge("document_orchestration", "document_generation")
    workflow.add_edge("document_generation", "consistency_check")
    
    workflow.add_conditional_edges(
        "consistency_check",
        lambda state: "document_orchestration" if state.status == "document_regeneration_required" else "export_to_pdf"
    )
    
    workflow.add_edge("export_to_pdf", END)
    
    return workflow.compile()

def visualize_workflow():
    """ワークフローを可視化"""
    # モックの初期状態を作成
    initial_state = MockGraphState()
    
    # ワークフローを作成
    app = create_mock_workflow()
    
    # グラフを取得
    graph = app.get_graph()
    
    # Graphvizで可視化
    dot = Digraph(comment='ワークフロー状態遷移図')
    dot.attr(rankdir='TB')  # 上から下へのレイアウト
    
    # サブグラフを使用してノードをグループ化
    with dot.subgraph(name='cluster_0') as c:
        c.attr(rank='same')
        c.node(START, "開始", shape='circle', style='filled', fillcolor='lightgreen')
        c.node("text_extraction", "テキスト抽出", shape='box', style='rounded,filled', fillcolor='lightblue')
    
    with dot.subgraph(name='cluster_1') as c:
        c.attr(rank='same')
        c.node("script_analysis", "スクリプト解析", shape='box', style='rounded,filled', fillcolor='lightblue')
        c.node("dynamic_grouping", "動的グループ化", shape='box', style='rounded,filled', fillcolor='lightblue')
    
    with dot.subgraph(name='cluster_2') as c:
        c.attr(rank='same')
        c.node("document_orchestration", "ドキュメント構造化", shape='box', style='rounded,filled', fillcolor='lightblue')
        c.node("document_generation", "ドキュメント生成", shape='box', style='rounded,filled', fillcolor='lightblue')
    
    with dot.subgraph(name='cluster_3') as c:
        c.attr(rank='same')
        c.node("consistency_check", "整合性チェック", shape='box', style='rounded,filled', fillcolor='lightblue')
    
    with dot.subgraph(name='cluster_4') as c:
        c.attr(rank='same')
        c.node("export_to_pdf", "PDF出力", shape='box', style='rounded,filled', fillcolor='lightblue')
        c.node(END, "終了", shape='circle', style='filled', fillcolor='lightgreen')
    
    # エッジのスタイル設定
    dot.attr('edge', color='gray')
    
    # エッジを追加
    for edge in graph.edges:
        if edge[0] == "consistency_check":
            if edge[1] == "document_orchestration":
                dot.edge(edge[0], edge[1], color='red', label='再生成必要')
            elif edge[1] == "export_to_pdf":
                dot.edge(edge[0], edge[1], color='green', label='チェック成功')
        elif edge[0] == "text_extraction" and edge[1] == "text_extraction":
            dot.edge(edge[0], edge[1], color='blue', label='抽出継続')
        else:
            dot.edge(edge[0], edge[1])
    
    # グラフを保存
    output_dir = "output/visualization"
    import os
    os.makedirs(output_dir, exist_ok=True)
    dot.render(os.path.join(output_dir, 'workflow'), format='png', cleanup=True)
    print(f"ワークフロー図が生成されました: {output_dir}/workflow.png")

if __name__ == "__main__":
    visualize_workflow() 