"""
ドキュメントの整合性チェックを行うノード
このモジュールは生成されたドキュメントの品質と正確性を検証します。
"""
from typing import Dict, List, Any
import json
import os

from pydantic import BaseModel, Field
from src.model_types import GraphState, ConsistencyCheckResult, ConsistencyCheckFeedback, DocumentSection
from src.utils.llm_utils import (
    get_llm,
    get_structured_llm,
    create_structured_prompt,
    CONSISTENCY_CHECK_SYSTEM_PROMPT,
    CONSISTENCY_CHECK_HUMAN_PROMPT
)
from src.utils.config import load_config


class ConsistencyCheckResponse(BaseModel):
    """整合性チェック結果のスキーマ"""
    detailed_feedback: List[ConsistencyCheckFeedback] = Field(
        description="カテゴリごとの詳細なフィードバック"
    )
    overall_score: float = Field(
        description="整合性の総合スコア（0.0-1.0）",
        ge=0.0,
        le=1.0
    )
    is_consistent: bool = Field(
        description="整合性があるかどうかのフラグ"
    )
    feedback: str = Field(
        description="全体的なフィードバックメッセージ"
    )


def check_consistency(state: GraphState) -> GraphState:
    """
    ドキュメントの整合性をチェックするノード
    
    各ドキュメントセクションについて、技術的正確性、完全性、明確性などの
    観点から整合性をチェックします。設定された閾値を下回る場合、
    そのセクションは不整合と判断され、詳細なフィードバックが提供されます。
    
    また、否定回数の上限を設けることで、無限ループを防ぎます。
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        更新されたグラフ状態
    """
    # 設定ファイルから整合性チェックの設定を読み込む
    config = load_config()
    consistency_config = config.get("consistency_check", {})
    # 否定の最大回数（デフォルト：3回）
    max_rejections = consistency_config.get("max_rejections", 3)
    # 否定を行う閾値（0.0-1.0、デフォルト：0.7）
    rejection_threshold = consistency_config.get("rejection_threshold", 0.7)
    
    # 各セクションについて整合性チェックを実行
    for section_id, section in state.document_sections.items():
        # 既存のチェック結果を取得または新規作成
        check_result = state.consistency_checks.get(
            section_id,
            ConsistencyCheckResult(section_id=section_id, is_consistent=False)
        )
        
        # 否定回数が上限に達している場合はスキップ
        if check_result.rejection_count >= max_rejections:
            print(f"セクション {section_id} は否定回数が上限({max_rejections}回)に達しているためスキップします")
            continue
        
        # セクションに関連するソースコード解析結果を収集
        analysis_results = _get_related_analysis_results(state, section)
        
        # LLMを使用してセクションの整合性をチェック
        result = _check_section_consistency(section, analysis_results)
        
        # 結果の評価と更新
        check_result.detailed_feedback = result["detailed_feedback"]
        check_result.overall_score = result["overall_score"]
        check_result.feedback = result["feedback"]
        
        # 整合性の判定（閾値を考慮）
        if result["overall_score"] < rejection_threshold:
            # スコアが閾値を下回る場合は不整合と判断
            check_result.is_consistent = False
            check_result.rejection_count += 1
        else:
            # スコアが閾値以上の場合は整合していると判断
            check_result.is_consistent = True
        
        # 状態を更新
        state.consistency_checks[section_id] = check_result
    
    # すべてのセクションが整合している、または否定回数上限に達している場合は完了
    all_consistent = all(
        result.is_consistent or result.rejection_count >= max_rejections
        for result in state.consistency_checks.values()
    )
    
    if all_consistent:
        # すべてのセクションが整合していると判断された場合、次のステップへ進む
        state.status = "consistency_check_complete"
    
    return state


def _get_related_analysis_results(state: GraphState, section: DocumentSection) -> List[Dict[str, Any]]:
    """
    セクションに関連するソースコード解析結果を取得
    
    セクションが属するグループに含まれるファイルの解析結果を収集します。
    これらの解析結果は整合性チェックの参照情報として使用されます。
    
    Args:
        state: グラフの状態
        section: ドキュメントセクション
    
    Returns:
        関連する解析結果のリスト
    """
    # セクションが属するグループを取得
    group = state.groups.get(section.group_id)
    if not group:
        return []
    
    # グループに含まれるファイルの解析結果を収集
    results = []
    for file_path in group.files:
        if file_path in state.analysis_results:
            results.append(state.analysis_results[file_path].model_dump())
    
    return results


def _check_section_consistency(
    section: DocumentSection,
    analysis_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    個別のセクションの整合性をチェック
    
    LLMを使用して、セクションの内容とソースコード解析結果を比較し、
    整合性を評価します。詳細なフィードバックと総合スコアが返されます。
    
    Args:
        section: チェック対象のセクション
        analysis_results: 関連する解析結果
    
    Returns:
        チェック結果（detailed_feedback, overall_score, is_consistent, feedbackを含む辞書）
    """
    try:
        # 構造化出力用のLLMを取得
        structured_llm = get_structured_llm(ConsistencyCheckResponse)
        
        # プロンプトの作成
        prompt = f"""
        以下のドキュメントセクションについて整合性をチェックし、詳細なフィードバックを提供してください。
        
        ## セクション情報
        セクションID: {section.section_id}
        タイトル: {section.title}
        
        ## セクション内容
        {section.content}
        
        ## 関連するソースコード解析結果
        {json.dumps(analysis_results, ensure_ascii=False, indent=2)}
        
        以下の観点からセクションの整合性を評価してください：
        1. 正確性：技術的な誤りや矛盾がないか
        2. 完全性：必要な情報がすべて含まれているか
        3. 明確性：説明が明確で理解しやすいか
        4. 構成：論理的な構造になっているか
        5. 一貫性：用語や概念が一貫して使用されているか
        
        各カテゴリについて詳細なフィードバックを提供し、0.0-1.0のスコアで評価してください。
        """
        
        # LLMに問い合わせ（構造化出力で直接Pydanticモデルとして取得）
        response = structured_llm.invoke(prompt)
        
        # 辞書形式に変換して返す
        return response.model_dump()
        
    except Exception as e:
        # エラー時のフォールバック
        print(f"整合性チェック結果の取得に失敗しました: {str(e)}")
        return {
            "detailed_feedback": [],
            "overall_score": 0.0,
            "is_consistent": False,
            "feedback": f"エラーが発生しました: {str(e)}"
        }


def _get_related_sections(state: GraphState, current_group_id: str, max_sections: int = 3) -> Dict[str, str]:
    """
    関連するセクションを取得
    
    現在のグループに関連する他のセクションを特定します。
    関連性の判断基準には、ファイルの依存関係や特定のグループ属性が使用されます。
    
    Args:
        state: グラフの現在の状態
        current_group_id: 現在のグループID
        max_sections: 取得する最大セクション数
    
    Returns:
        関連セクションの辞書 (セクションID -> セクション内容)
    """
    related_sections = {}
    
    # 特殊なグループIDの場合の処理
    if current_group_id in ["system_overview", "system_interfaces", "business_logic"]:
        # システム全体に関連するセクションは他のすべてのセクションと関連がある
        count = 0
        for section_id, section in state.document_sections.items():
            if section.group_id != current_group_id:
                # 各関連セクションの概要（最初の500文字）を取得
                related_sections[section_id] = f"タイトル: {section.title}\n\n{section.content[:500]}...(省略)"
                count += 1
                if count >= max_sections:
                    break
        return related_sections
    
    # 通常のグループの場合
    # 現在のグループに関連するグループを特定（同じファイルを参照しているなど）
    all_dependencies = set()
    
    # グループにファイルが含まれている場合のみ処理
    if current_group_id in state.groups and state.groups[current_group_id].files:
        for file_path in state.groups[current_group_id].files:
            if file_path in state.analysis_results:
                # ファイルの依存関係を収集
                all_dependencies.update(state.analysis_results[file_path].dependencies)
    
    # 関連するグループを見つける
    related_groups = []
    for group_id, group in state.groups.items():
        if group_id == current_group_id:
            continue
        
        # 依存関係のあるファイルを含むグループを探す
        group_files_set = set(group.files)
        for dep in all_dependencies:
            for file in group_files_set:
                if dep in file:
                    related_groups.append(group_id)
                    break
            if group_id in related_groups:
                break
    
    # 関連グループに対応するセクションを取得
    count = 0
    for section_id, section in state.document_sections.items():
        if section.group_id in related_groups:
            # 各関連セクションの概要（最初の500文字）を取得
            related_sections[section_id] = f"タイトル: {section.title}\n\n{section.content[:500]}...(省略)"
            count += 1
            if count >= max_sections:
                break
    
    # 関連するセクションが見つからなかった場合は、システム概要セクションを関連セクションとして追加
    if not related_sections:
        for section_id, section in state.document_sections.items():
            if section.group_id == "system_overview":
                related_sections[section_id] = f"タイトル: {section.title}\n\n{section.content[:500]}...(省略)"
                break
    
    return related_sections


def _check_overall_document_consistency(state: GraphState) -> ConsistencyCheckResult:
    """
    ドキュメント全体の整合性をチェック
    
    すべてのセクションを考慮して、ドキュメント全体の一貫性、構造、
    相互参照などを評価します。
    
    Args:
        state: グラフの現在の状態
    
    Returns:
        整合性チェックの結果
    """
    # すべてのセクションのタイトルと概要を収集
    sections_summary = []
    for section_id, section in sorted(state.document_sections.items(), key=lambda x: x[1].order):
        # 各セクションの最初の300文字を抽出して概要とする
        content_summary = section.content[:300] + "..." if len(section.content) > 300 else section.content
        sections_summary.append(f"## {section.title}\n{content_summary}\n")
    
    all_sections_text = "\n".join(sections_summary)
    
    # LLMを使用して整合性チェック
    llm = get_llm()
    
    # 全体チェック用のプロンプト
    prompt_template = f"""
あなたはソフトウェアドキュメントの品質と整合性を検証する専門家です。
以下のドキュメント全体の整合性をチェックしてください。

# ドキュメントの全体構成
{all_sections_text}

ドキュメント全体について、以下の観点から評価してください：

1. **全体構成**: 論理的な流れになっているか、必要なセクションは全て含まれているか
2. **用語の一貫性**: 同じ概念や機能に対して一貫した用語が使われているか
3. **重複と矛盾**: 異なるセクションで同じ内容が重複していないか、矛盾した情報はないか
4. **情報の網羅性**: システム全体を理解するために必要な情報がカバーされているか
5. **セクション間の参照関係**: セクション間の相互参照が適切か

JSON形式で回答してください：

```json
{{
  "section_id": "overall_consistency_check",
  "is_consistent": true/false,
  "feedback": "全体的な整合性に関するフィードバック（問題点や改善提案を含む）"
}}
```
"""
    
    # LLMに問い合わせ
    response = llm.invoke([{"role": "user", "content": prompt_template}])
    response_text = response.content
    
    # JSONレスポンスを抽出して解析
    try:
        # JSONブロックを抽出
        json_start = response_text.find('```json') + 7 if '```json' in response_text else 0
        json_end = response_text.find('```', json_start) if '```' in response_text[json_start:] else len(response_text)
        json_str = response_text[json_start:json_end].strip()
        
        # JSONをパース
        check_data = json.loads(json_str)
        
        return ConsistencyCheckResult(
            section_id="overall_consistency_check",
            is_consistent=check_data.get("is_consistent", True),
            feedback=check_data.get("feedback", None)
        )
    
    except json.JSONDecodeError as e:
        # JSONパースエラー時のフォールバック
        print(f"全体整合性チェック結果のパースに失敗しました: {str(e)}")
        return ConsistencyCheckResult(
            section_id="overall_consistency_check",
            is_consistent=False,
            feedback=f"パースエラー: 全体整合性チェック結果を解析できませんでした。"
        )


def _save_consistency_check(result: ConsistencyCheckResult, output_dir: str = "./output/consistency") -> None:
    """
    整合性チェック結果をJSONファイルとして保存
    
    チェック結果を永続化し、後で参照できるようにします。
    
    Args:
        result: 整合性チェック結果
        output_dir: 出力ディレクトリ
    """
    # 出力ディレクトリがなければ作成
    os.makedirs(output_dir, exist_ok=True)
    
    # 出力ファイルパスの設定
    output_file = os.path.join(output_dir, f"{result.section_id}.json")
    
    # JSONとして保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2) 