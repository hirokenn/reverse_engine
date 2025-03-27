from typing import Dict, List, Any, Optional
import json
import os
import uuid

from src.model_types import GraphState, GroupInfo, FileAnalysisResult
from src.utils.llm_utils import (
    get_llm,
    create_structured_prompt,
    GROUP_ANALYSIS_SYSTEM_PROMPT,
    GROUP_ANALYSIS_HUMAN_PROMPT
)


def dynamic_grouping(state: GraphState) -> GraphState:
    """
    ファイル解析結果を元にグループ化するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    if state.status != "script_analysis_complete":
        # スクリプト解析が完了していない場合はスキップ
        return state
    
    print("ファイルのグループ化を開始します...")
    
    # 解析結果の取得
    analysis_results = list(state.analysis_results.values())
    
    # グループ情報の初期化
    if not state.groups:
        state.groups = {}
    
    # 各ファイルを処理
    for result in analysis_results:
        if any(result.file_path in group.files for group in state.groups.values()):
            # すでにグループに割り当てられている場合はスキップ
            continue
        
        # グループの割り当て（または新規作成）
        _assign_file_to_group(state, result)
    
    # グループの概要を生成
    for group_id, group in state.groups.items():
        if not group.summary:
            group.summary = _generate_group_summary(state, group)
    
    state.status = "grouping_complete"
    
    # グループ情報をJSONファイルとして保存（オプション）
    _save_groups_info(state.groups)
    
    return state


def _assign_file_to_group(state: GraphState, file_analysis: FileAnalysisResult) -> None:
    """
    ファイルを適切なグループに割り当て
    
    Args:
        state: グラフの現在の状態
        file_analysis: ファイル解析結果
    """
    # 既存グループ情報の整形
    existing_groups_info = ""
    if state.groups:
        for group_id, group in state.groups.items():
            existing_groups_info += f"グループID: {group_id}\n"
            existing_groups_info += f"グループ名: {group.group_name}\n"
            existing_groups_info += f"説明: {group.description}\n"
            existing_groups_info += f"ファイル: {', '.join(group.files)}\n\n"
    else:
        existing_groups_info = "既存のグループはありません。"
    
    # ファイル解析情報の整形
    file_info = f"""
ファイルパス: {file_analysis.file_path}
ファイルタイプ: {file_analysis.file_type}
要約: {file_analysis.summary}
目的: {file_analysis.purpose}
機能数: {len(file_analysis.functions)}
依存関係: {', '.join(file_analysis.dependencies)}
ビジネスルール: {', '.join(file_analysis.business_rules) if file_analysis.business_rules else 'なし'}
"""
    
    # LLMを使用してグループを判断
    llm = get_llm()
    
    prompt = create_structured_prompt(
        system_message=GROUP_ANALYSIS_SYSTEM_PROMPT,
        human_template=GROUP_ANALYSIS_HUMAN_PROMPT,
        input_variables={
            "file_analysis": file_info,
            "existing_groups": existing_groups_info
        }
    )
    
    response = llm.invoke(prompt)
    response_text = response.content
    
    # JSONレスポンスを抽出して解析
    try:
        json_start = response_text.find('```json') + 7 if '```json' in response_text else 0
        json_end = response_text.find('```', json_start) if '```' in response_text[json_start:] else len(response_text)
        json_str = response_text[json_start:json_end].strip()
        
        # JSONをパース
        group_decision = json.loads(json_str)
        
        if group_decision.get("group_id") == "new":
            # 新しいグループを作成
            new_group_id = f"group_{str(uuid.uuid4())[:8]}"
            new_group = GroupInfo(
                group_id=new_group_id,
                group_name=group_decision.get("group_name", "未名称グループ"),
                description=group_decision.get("description", "説明なし"),
                files=[file_analysis.file_path]
            )
            state.groups[new_group_id] = new_group
            print(f"新しいグループを作成しました: {new_group.group_name} - {file_analysis.file_path}")
        else:
            # 既存のグループに追加
            group_id = group_decision.get("group_id")
            if group_id in state.groups:
                state.groups[group_id].files.append(file_analysis.file_path)
                print(f"既存グループに追加しました: {state.groups[group_id].group_name} - {file_analysis.file_path}")
            else:
                print(f"指定されたグループIDが見つかりません: {group_id}")
                # 見つからない場合は、デフォルトグループを作成
                default_group_id = "default_group"
                if default_group_id not in state.groups:
                    state.groups[default_group_id] = GroupInfo(
                        group_id=default_group_id,
                        group_name="その他",
                        description="自動分類できなかったファイル",
                        files=[file_analysis.file_path]
                    )
                else:
                    state.groups[default_group_id].files.append(file_analysis.file_path)
    
    except json.JSONDecodeError as e:
        print(f"グループ判断のパースに失敗しました: {str(e)}")
        # エラーが発生した場合は、デフォルトグループに追加
        default_group_id = "default_group"
        if default_group_id not in state.groups:
            state.groups[default_group_id] = GroupInfo(
                group_id=default_group_id,
                group_name="その他",
                description="自動分類できなかったファイル",
                files=[file_analysis.file_path]
            )
        else:
            state.groups[default_group_id].files.append(file_analysis.file_path)


def _generate_group_summary(state: GraphState, group: GroupInfo) -> str:
    """
    グループの概要を生成
    
    Args:
        state: グラフの現在の状態
        group: グループ情報
    
    Returns:
        グループの概要
    """
    llm = get_llm()
    
    # グループに含まれるファイルの解析結果を集約
    files_info = []
    for file_path in group.files:
        if file_path in state.analysis_results:
            result = state.analysis_results[file_path]
            files_info.append(f"ファイル: {file_path}\n要約: {result.summary}\n目的: {result.purpose}\n")
    
    files_summary = "\n".join(files_info)
    
    # 概要生成プロンプト
    prompt_template = f"""
あなたはシステム分析の専門家です。以下のファイルグループの目的や特徴を簡潔に要約してください。

グループ名: {group.group_name}
グループ説明: {group.description}

このグループに含まれるファイル:
{files_summary}

このグループ全体の目的と特徴を200-300文字程度で要約してください。
"""
    
    # LLMに問い合わせ
    response = llm.invoke([{"role": "user", "content": prompt_template}])
    
    return response.content


def _save_groups_info(groups: Dict[str, GroupInfo], output_dir: str = "./output/groups") -> None:
    """
    グループ情報をJSONファイルとして保存
    
    Args:
        groups: グループ情報
        output_dir: 出力ディレクトリ
    """
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "groups.json")
    
    # JSONに変換
    groups_data = {
        group_id: group.model_dump()
        for group_id, group in groups.items()
    }
    
    # ファイルに保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(groups_data, f, ensure_ascii=False, indent=2)