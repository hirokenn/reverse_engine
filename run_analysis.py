#!/usr/bin/env python3
"""
source_codeフォルダのソースコードを解析するシンプルなコマンドラインスクリプト
"""
import os
import sys
import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.app import create_workflow_from_folder, load_config, create_workflow
from src.utils.file_utils import get_file_list
from src.model_types import GraphState

# 可視化用のライブラリをインポート
import matplotlib.pyplot as plt
import networkx as nx
from langgraph.graph import StateGraph

# source_codeフォルダのパス
SOURCE_CODE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_code")


def print_status(message: str):
    """ステータスメッセージを表示"""
    print(f"\033[1;34m[INFO]\033[0m {message}")


def print_error(message: str):
    """エラーメッセージを表示"""
    print(f"\033[1;31m[ERROR]\033[0m {message}")


def print_success(message: str):
    """成功メッセージを表示"""
    print(f"\033[1;32m[SUCCESS]\033[0m {message}")


def visualize_workflow_graph(workflow: StateGraph, output_path: str = "workflow_graph.png"):
    """
    ワークフローグラフ構造を可視化して保存する
    
    Args:
        workflow: 可視化するStateGraphオブジェクト
        output_path: 出力先ファイルパス
    """
    try:
        print_status(f"グラフ構造の可視化を開始します...")
        
        # グラフデータの取得
        internal_graph = workflow.graph
        
        # NetworkXグラフオブジェクトを作成
        G = nx.DiGraph()
        
        # ノードを追加
        for node in internal_graph.nodes:
            G.add_node(node)
        
        # エッジを追加
        for source, targets in internal_graph.edges.items():
            for target in targets:
                G.add_edge(source, target)
        
        # グラフの描画設定
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42)  # レイアウトを決定
        
        # ノードの描画
        nx.draw_networkx_nodes(G, pos, node_size=2000, node_color="lightblue", alpha=0.8)
        
        # エッジの描画
        nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.7, arrows=True, arrowsize=20)
        
        # ノードラベルの描画
        nx.draw_networkx_labels(G, pos, font_size=10, font_family="sans-serif")
        
        # タイトルとグリッドの設定
        plt.title("ワークフローグラフ構造", fontsize=15)
        plt.axis("off")  # 軸を非表示
        
        # グラフを保存
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        
        print_success(f"グラフ構造を {output_path} に保存しました")
        return True
        
    except Exception as e:
        print_error(f"グラフ可視化中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def visualize_dependency_graph(state: GraphState, output_path: str = "dependency_graph.png"):
    """
    解析されたファイル間の依存関係グラフを可視化して保存する
    
    Args:
        state: 解析結果を含むGraphStateオブジェクト
        output_path: 出力先ファイルパス
    """
    try:
        print_status(f"依存関係グラフの可視化を開始します...")
        
        # グラフを作成
        G = nx.DiGraph()
        
        # 解析結果からノードを追加
        for file_path, analysis in state.analysis_results.items():
            file_name = os.path.basename(file_path)
            G.add_node(file_name, path=file_path, type=analysis.file_type)
        
        # 依存関係をエッジとして追加
        for file_path, analysis in state.analysis_results.items():
            source_name = os.path.basename(file_path)
            for dependency in analysis.dependencies:
                # 依存パスからファイル名を取得
                if os.path.isabs(dependency):
                    dep_name = os.path.basename(dependency)
                else:
                    dep_name = os.path.basename(dependency)
                
                # 依存関係がグラフにあればエッジを追加
                if any(os.path.basename(path) == dep_name for path in state.analysis_results.keys()):
                    G.add_edge(source_name, dep_name)
        
        # ノード数が多すぎる場合は警告
        if len(G.nodes) > 100:
            print_status(f"ノード数が多いため、グラフが複雑になる可能性があります ({len(G.nodes)}ノード)")
        
        # グラフの描画設定
        plt.figure(figsize=(16, 12))
        
        # レイアウトを計算（大規模グラフの場合はkamada_kawaiを使用）
        if len(G.nodes) > 50:
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42)
        
        # ファイルタイプで色分け
        file_types = {data.get('type', 'unknown') for _, data in G.nodes(data=True)}
        color_map = plt.cm.get_cmap('tab10', len(file_types))
        type_to_color = {t: color_map(i/len(file_types)) for i, t in enumerate(file_types)}
        
        node_colors = [type_to_color.get(G.nodes[n].get('type', 'unknown'), 'gray') for n in G.nodes()]
        
        # ノードの描画
        nx.draw_networkx_nodes(G, pos, node_size=1000, node_color=node_colors, alpha=0.8)
        
        # エッジの描画
        nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.6, arrows=True, arrowsize=15)
        
        # ノードラベルの描画
        nx.draw_networkx_labels(G, pos, font_size=8, font_family="sans-serif")
        
        # 凡例の作成
        legend_handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, 
                                    markersize=10, label=file_type) 
                        for file_type, color in type_to_color.items()]
        plt.legend(handles=legend_handles, title="ファイルタイプ")
        
        # タイトルとグリッドの設定
        plt.title("ファイル依存関係グラフ", fontsize=15)
        plt.axis("off")  # 軸を非表示
        
        # グラフを保存
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        
        print_success(f"依存関係グラフを {output_path} に保存しました")
        return True
        
    except Exception as e:
        print_error(f"依存関係グラフ可視化中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def visualize_groups(state: GraphState, output_path: str = "group_structure.png"):
    """
    ファイルグループ構造を可視化して保存する
    
    Args:
        state: 解析結果を含むGraphStateオブジェクト
        output_path: 出力先ファイルパス
    """
    try:
        print_status(f"グループ構造の可視化を開始します...")
        
        # グラフを作成
        G = nx.Graph()
        
        # グループをノードとして追加
        for group_id, group_info in state.groups.items():
            G.add_node(group_id, 
                      name=group_info.group_name, 
                      description=group_info.description,
                      file_count=len(group_info.files))
        
        # ファイルを追加してグループと接続
        for file_path in state.analysis_results.keys():
            file_name = os.path.basename(file_path)
            G.add_node(file_name, type='file')
            
            # ファイルが属するグループを探す
            for group_id, group_info in state.groups.items():
                if file_path in group_info.files:
                    G.add_edge(group_id, file_name)
        
        # グラフの描画設定
        plt.figure(figsize=(16, 12))
        pos = nx.spring_layout(G, seed=42)
        
        # ノードタイプを分類
        group_nodes = [n for n in G.nodes() if n in state.groups]
        file_nodes = [n for n in G.nodes() if n not in state.groups]
        
        # グループノードの描画（サイズはファイル数に比例）
        group_sizes = [G.nodes[n]['file_count'] * 300 for n in group_nodes]
        nx.draw_networkx_nodes(G, pos, nodelist=group_nodes, node_size=group_sizes, 
                              node_color="lightgreen", alpha=0.8)
        
        # ファイルノードの描画
        nx.draw_networkx_nodes(G, pos, nodelist=file_nodes, node_size=100, 
                              node_color="lightskyblue", alpha=0.6)
        
        # エッジの描画
        nx.draw_networkx_edges(G, pos, width=0.8, alpha=0.5)
        
        # グループノードのラベル描画
        group_labels = {n: G.nodes[n]['name'] for n in group_nodes}
        nx.draw_networkx_labels(G, pos, labels=group_labels, font_size=10, font_weight='bold')
        
        # ファイルノードのラベル描画（小さく表示）
        file_labels = {n: n for n in file_nodes}
        nx.draw_networkx_labels(G, pos, labels=file_labels, font_size=6)
        
        # タイトルとグリッドの設定
        plt.title("ファイルグループ構造", fontsize=15)
        plt.axis("off")  # 軸を非表示
        
        # グラフを保存
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        
        print_success(f"グループ構造を {output_path} に保存しました")
        return True
        
    except Exception as e:
        print_error(f"グループ構造可視化中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def analyze_folder(folder_path: str, config_path: Optional[str] = None, visualize: bool = False, 
                  output_dir: str = "./output/graphs"):
    """指定フォルダのソースコードを解析する"""
    try:
        print_status(f"解析対象フォルダ: {folder_path}")
        
        # フォルダが存在するか確認
        if not os.path.exists(folder_path):
            print_error(f"指定されたフォルダが存在しません: {folder_path}")
            return False
        
        # 設定を読み込む
        config = load_config(config_path)
        print_status("設定を読み込みました")
        
        # 可視化用の出力ディレクトリを作成
        if visualize:
            os.makedirs(output_dir, exist_ok=True)
            print_status(f"可視化結果の出力先: {output_dir}")
        
        # ファイルリストを取得
        file_paths = get_file_list(folder_path, config)
        
        if not file_paths:
            print_error(f"解析可能なファイルが見つかりませんでした: {folder_path}")
            return False
        
        # ファイル数と拡張子別のカウントを表示
        extensions = {}
        for file_path in file_paths:
            ext = os.path.splitext(file_path)[1].lower()
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1
        
        print_status(f"合計 {len(file_paths)} 個のファイルを解析します")
        for ext, count in extensions.items():
            print(f"  - {ext}: {count}ファイル")
        
        # ワークフローと初期状態を作成
        print_status("ワークフローを初期化しています...")
        workflow, initial_state = create_workflow_from_folder(folder_path, config)
        
        # ワークフローグラフ構造を可視化
        if visualize:
            workflow_graph_path = os.path.join(output_dir, "workflow_graph.png")
            visualize_workflow_graph(workflow, workflow_graph_path)
        
        # 実行可能なグラフを作成
        app = workflow.compile()
        
        # 前回の状態を保存
        prev_status = None
        final_state = None
        
        # ワークフローを実行
        print_status("解析を開始します...")
        for state in app.stream(initial_state):
            status = state.status
            final_state = state
            
            # 状態が変わった場合のみメッセージを表示
            if status != prev_status:
                if status == "script_analysis_initialized":
                    print_status("スクリプト解析を初期化しています...")
                elif status == "script_analysis_complete":
                    print_success("スクリプト解析が完了しました")
                    print_status("ファイルのグループ化を実行しています...")
                    
                    # 依存関係グラフを可視化
                    if visualize:
                        dependency_graph_path = os.path.join(output_dir, "dependency_graph.png")
                        visualize_dependency_graph(state, dependency_graph_path)
                elif status == "grouping_complete":
                    print_success("ファイルのグループ化が完了しました")
                    print_status("ドキュメント生成を実行しています...")
                    
                    # グループ構造を可視化
                    if visualize:
                        group_structure_path = os.path.join(output_dir, "group_structure.png")
                        visualize_groups(state, group_structure_path)
                elif status == "document_generation_complete":
                    print_success("ドキュメント生成が完了しました")
                    print_status("整合性チェックを実行しています...")
                elif status == "consistency_check_complete":
                    print_success("整合性チェックが完了しました")
                    print_status("ドキュメント構成を生成しています...")
                elif status == "document_outline_complete":
                    print_success("ドキュメント構成の生成が完了しました")
                
                prev_status = status
            
            # スクリプト解析の進捗状況を表示
            if status == "script_analysis_initialized":
                current_file = state.current_file_index
                total_files = state.total_files
                
                if current_file > 0:
                    progress = int((current_file / total_files) * 100)
                    sys.stdout.write(f"\r解析進捗: {current_file}/{total_files} ファイル ({progress}%)")
                    sys.stdout.flush()
        
        # 解析が完了したらメッセージを表示
        print("\n")
        print_success("解析が完了しました")
        
        # 結果の出力先を表示
        output_documents_dir = config.get("output_dir", "./output")
        print_status(f"生成されたドキュメントは {output_documents_dir} ディレクトリに保存されています")
        
        if visualize:
            print_status(f"可視化されたグラフは {output_dir} ディレクトリに保存されています")
        
        return True
        
    except Exception as e:
        print_error(f"解析中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="ソースコードの解析を実行するスクリプト")
    
    parser.add_argument(
        "--folder", "-f", 
        type=str, 
        default=SOURCE_CODE_DIR,
        help=f"解析対象のフォルダパス (デフォルト: {SOURCE_CODE_DIR})"
    )
    
    parser.add_argument(
        "--config", "-c", 
        type=str, 
        default=None,
        help="設定ファイルのパス (デフォルト: ./config/config.json)"
    )
    
    parser.add_argument(
        "--visualize", "-v", 
        action="store_true",
        help="解析結果をグラフとして可視化する"
    )
    
    parser.add_argument(
        "--output-dir", "-o", 
        type=str, 
        default="./output/graphs",
        help="可視化結果の出力先ディレクトリ (デフォルト: ./output/graphs)"
    )
    
    args = parser.parse_args()
    
    # フォルダパスを絶対パスに変換
    folder_path = os.path.abspath(args.folder)
    
    # 解析を実行
    success = analyze_folder(
        folder_path=folder_path, 
        config_path=args.config,
        visualize=args.visualize,
        output_dir=args.output_dir
    )
    
    # 終了コードを設定
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 