from typing import Dict, List, Any
import json
import os

from src.model_types import GraphState, DocumentOutline
from src.utils.file_utils import save_json, save_markdown, markdown_to_html
from src.utils.llm_utils import (
    get_llm,
    create_structured_prompt,
    DOCUMENT_OUTLINE_SYSTEM_PROMPT,
    DOCUMENT_OUTLINE_HUMAN_PROMPT
)


def generate_document_outline(state: GraphState) -> GraphState:
    """
    ドキュメント全体のアウトライン（目次）を生成するノード
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    if state.status != "consistency_check_complete":
        # 整合性チェックが完了していない場合はスキップ
        return state
    
    print("ドキュメント全体のアウトラインを生成します...")
    
    # グループ情報と整合性チェック結果を準備
    groups_info = _prepare_groups_info(state)
    consistency_feedback = _prepare_consistency_feedback(state)
    
    # 全体的な整合性チェック結果を取得
    overall_consistency = _get_overall_consistency_feedback(state)
    
    # LLMを使用してアウトラインを生成
    outline = _generate_outline_with_llm(groups_info, consistency_feedback, overall_consistency)
    
    # アウトラインを状態に追加
    state.document_outline = outline
    
    # アウトラインをJSONとして保存
    _save_document_outline(outline)
    
    # 最終的なドキュメントを生成
    _generate_final_document(state)
    
    state.status = "document_outline_complete"
    state.is_complete = True
    
    return state


def _prepare_groups_info(state: GraphState) -> str:
    """
    グループ情報を整形
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        整形されたグループ情報
    """
    groups_text = ""
    
    # まずシステム全体のセクションを抽出
    system_sections = []
    for section_id, section in state.document_sections.items():
        if section.group_id in ["system_overview", "system_interfaces", "business_logic"]:
            system_sections.append({
                "section_id": section_id,
                "title": section.title,
                "group_id": section.group_id,
                "order": section.order
            })
    
    # システム全体のセクション情報を追加
    if system_sections:
        groups_text += "## システム全体のセクション\n"
        for section in sorted(system_sections, key=lambda s: s["order"]):
            groups_text += f"セクションID: {section['section_id']}\n"
            groups_text += f"タイトル: {section['title']}\n"
            groups_text += f"タイプ: {section['group_id']}\n\n"
    
    # 通常のグループ情報を追加
    groups_text += "## 機能グループ\n"
    for group_id, group in state.groups.items():
        # 特殊なシステム全体グループはスキップ
        if group_id in ["system_overview", "system_interfaces", "business_logic"]:
            continue
            
        groups_text += f"グループID: {group_id}\n"
        groups_text += f"グループ名: {group.group_name}\n"
        groups_text += f"説明: {group.description}\n"
        groups_text += f"ファイル数: {len(group.files)}\n"
        
        if group.summary:
            groups_text += f"概要: {group.summary}\n"
        
        # セクション情報を追加
        section = next((s for s in state.document_sections.values() if s.group_id == group_id), None)
        if section:
            groups_text += f"セクションID: {section.section_id}\n"
            groups_text += f"セクションタイトル: {section.title}\n"
        
        groups_text += "\n"
    
    return groups_text


def _prepare_consistency_feedback(state: GraphState) -> str:
    """
    整合性チェック結果を整形
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        整形された整合性チェック結果
    """
    feedback_text = "## 個別セクションの整合性チェック結果\n\n"
    has_issues = False
    
    for check_id, check in state.consistency_checks.items():
        # 全体チェックはスキップ
        if check_id == "overall_consistency_check":
            continue
            
        if not check.is_consistent and check.feedback:
            has_issues = True
            section = state.document_sections.get(check.section_id)
            if section:
                feedback_text += f"セクション '{section.title}' の問題点:\n"
                feedback_text += f"{check.feedback}\n\n"
    
    if not has_issues:
        feedback_text += "個別セクションの整合性チェックでは特に問題は見つかりませんでした。\n\n"
    
    return feedback_text


def _get_overall_consistency_feedback(state: GraphState) -> str:
    """
    全体的な整合性チェック結果を取得
    
    Args:
        state: グラフの現在の状態
        
    Returns:
        全体的な整合性チェック結果
    """
    # 全体チェック結果を探す
    overall_check = state.consistency_checks.get("overall_consistency_check")
    
    if not overall_check:
        return "全体的な整合性チェックの結果はありません。"
    
    result = "## 全体的な整合性チェック結果\n\n"
    
    if overall_check.is_consistent:
        result += "ドキュメント全体の整合性チェックでは特に問題は見つかりませんでした。\n\n"
    else:
        result += f"ドキュメント全体の整合性に関する問題点:\n{overall_check.feedback}\n\n"
    
    return result

def _generate_outline_with_llm(
    groups_info: str, 
    consistency_feedback: str,
    overall_consistency: str
) -> DocumentOutline:
    """
    LLMを使用してアウトラインを生成
    
    Args:
        groups_info: グループ情報
        consistency_feedback: 整合性チェック結果
        overall_consistency: 全体的な整合性チェック結果
        
    Returns:
        ドキュメントアウトライン
    """
    llm = get_llm()
    
    # プロンプトテンプレートを拡張
    extended_prompt = f"""
あなたはシステム仕様書の構成と設計を専門とする技術ドキュメント専門家です。
レガシーシステムの解析結果に基づいて、全体の仕様書のアウトライン（目次）を作成してください。

# グループ情報
{groups_info}

# 整合性チェック結果
{consistency_feedback}

# 全体的な整合性評価
{overall_consistency}

この情報を元に、以下の点に注意して仕様書の全体構成を設計してください:

1. 整合性チェックで指摘された問題点を解決する構成にする
2. システム全体を論理的に説明できる流れにする
3. 専門的で詳細な技術文書として適切な構成にする
4. 必要に応じて付録を追加して補足情報を提供する

以下のJSON形式で回答してください:

```json
{{
  "title": "システム全体のタイトル",
  "introduction": "序論の概要（詳細に記述）",
  "sections": [
    {{
      "id": "セクションID",
      "title": "セクションタイトル",
      "description": "このセクションの概要（詳細に記述）",
      "subsections": [
        {{
k          "id": "サブセクションID",
          "title": "サブセクションタイトル",
          "group_id": "関連するグループID（該当する場合）"
        }}
      ]
    }}
  ],
  "appendices": [
    {{
      "id": "付録ID",
      "title": "付録タイトル",
      "description": "この付録の概要（50-100字）"
    }}
  ]
}}
```
"""
    
    response = llm.invoke([{"role": "user", "content": extended_prompt}])
    response_text = response.content
    
    # JSONレスポンスを抽出して解析
    try:
        json_start = response_text.find('```json') + 7 if '```json' in response_text else 0
        json_end = response_text.find('```', json_start) if '```' in response_text[json_start:] else len(response_text)
        json_str = response_text[json_start:json_end].strip()
        
        # JSONをパース
        outline_data = json.loads(json_str)
        
        # DocumentOutlineに変換
        return DocumentOutline(**outline_data)
    
    except (json.JSONDecodeError, Exception) as e:
        print(f"アウトライン生成結果のパースに失敗しました: {str(e)}")
        # 最小限のアウトラインを返す
        return DocumentOutline(
            title="レガシーシステム仕様書",
            introduction="解析されたレガシーシステムの概要と仕様をまとめたドキュメントです。",
            sections=[],
            appendices=[]
        )


def _save_document_outline(outline: DocumentOutline, output_dir: str = "./output") -> None:
    """
    ドキュメントアウトラインをJSONとして保存
    
    Args:
        outline: ドキュメントアウトライン
        output_dir: 出力ディレクトリ
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # JSONとして保存
    json_path = os.path.join(output_dir, "document_outline.json")
    save_json(outline.model_dump(), json_path)


def _generate_final_document(state: GraphState, output_dir: str = "./output") -> None:
    """
    最終的なドキュメントを生成
    
    Args:
        state: グラフの現在の状態
        output_dir: 出力ディレクトリ
    """
    if not state.document_outline:
        print("ドキュメントアウトラインがありません。最終ドキュメントを生成できません。")
        return
    
    # Markdownドキュメントを作成
    outline = state.document_outline
    md_content = f"# {outline.title}\n\n## 概要\n\n{outline.introduction}\n\n"
    
    # 目次を追加
    md_content += "## 目次\n\n"
    for i, section in enumerate(outline.sections, 1):
        md_content += f"{i}. [{section['title']}](#section-{i})\n"
        for j, subsection in enumerate(section.get('subsections', []), 1):
            md_content += f"   {i}.{j}. [{subsection['title']}](#section-{i}-{j})\n"
    
    md_content += "\n"
    
    # セクションの内容を追加
    for i, section in enumerate(outline.sections, 1):
        md_content += f"<a id='section-{i}'></a>\n"
        md_content += f"## {i}. {section['title']}\n\n"
        
        if 'description' in section:
            md_content += f"{section['description']}\n\n"
        
        # サブセクションを追加
        for j, subsection in enumerate(section.get('subsections', []), 1):
            md_content += f"<a id='section-{i}-{j}'></a>\n"
            md_content += f"### {i}.{j}. {subsection['title']}\n\n"
            
            # グループIDが指定されている場合、対応するセクションの内容を取得
            group_id = subsection.get('group_id')
            if group_id:
                section_content = None
                for doc_section in state.document_sections.values():
                    if doc_section.group_id == group_id:
                        section_content = doc_section.content
                        break
                
                if section_content:
                    # 見出しレベルを調整
                    section_content = section_content.replace('# ', '#### ')
                    section_content = section_content.replace('## ', '##### ')
                    section_content = section_content.replace('### ', '###### ')
                    
                    md_content += f"{section_content}\n\n"
                else:
                    md_content += "このセクションのコンテンツは利用できません。\n\n"
    
    # 整合性チェック結果から改善点があれば追記
    overall_check = state.consistency_checks.get("overall_consistency_check")
    if overall_check and not overall_check.is_consistent and overall_check.feedback:
        md_content += "## 改善と検討事項\n\n"
        md_content += "このドキュメントには以下の改善点があります：\n\n"
        md_content += f"{overall_check.feedback}\n\n"
    
    # 付録を追加
    if outline.appendices:
        md_content += "## 付録\n\n"
        for i, appendix in enumerate(outline.appendices, 1):
            md_content += f"### 付録 {i}: {appendix['title']}\n\n"
            if 'description' in appendix:
                md_content += f"{appendix['description']}\n\n"
    
    # 生成日時を追加
    from datetime import datetime
    now = datetime.now()
    md_content += f"\n\n---\n\n*このドキュメントは自動生成されました。生成日時: {now.strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    # ファイルとして保存
    md_path = os.path.join(output_dir, "specification.md")
    save_markdown(md_content, md_path)
    
    # HTMLとしても保存
    html_path = os.path.join(output_dir, "specification.html")
    markdown_to_html(md_content, html_path)
    
    print(f"最終ドキュメントが生成されました: {md_path}")
    print(f"HTML形式のドキュメント: {html_path}") 