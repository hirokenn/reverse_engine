from typing import Dict, List, Any, Optional, Union
import os
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.output_parsers import PydanticOutputParser
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from pydantic import BaseModel


def get_llm(model_name: str = "gpt-3.5-turbo", temperature: float = 0.0, streaming: bool = False):
    """LLMインスタンスを取得します"""
    
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else None
    
    return ChatOpenAI(
        model_name=model_name,
        temperature=temperature,
        streaming=streaming,
        callbacks=callbacks,
    )


def create_structured_prompt(system_message: str, human_template: str, input_variables: Dict[str, Any]):
    """構造化されたプロンプトを作成します"""
    
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_message),
        HumanMessagePromptTemplate.from_template(human_template)
    ])
    
    return chat_prompt.format_messages(**input_variables)


def format_json_output(output: Dict[str, Any], indent: int = 2) -> str:
    """
    JSONの出力を整形します
    
    Args:
        output: 出力辞書
        indent: インデントサイズ
        
    Returns:
        整形されたJSON文字列
    """
    import json
    return json.dumps(output, ensure_ascii=False, indent=indent)


def get_structured_llm(model: Optional[BaseModel], model_name: str = "gpt-3.5-turbo", temperature: float = 0.0, streaming: bool = False):
    """
    構造化出力用のLLMインスタンスを取得します
    
    Args:
        model: Pydanticモデル
        model_name: モデル名
        temperature: 温度
        streaming: ストリーミング有効フラグ
        
    Returns:
        構造化出力に対応したLLM
    """
    llm = get_llm(model_name, temperature, streaming)
    return llm.with_structured_output(model)


def parse_llm_response_to_model(llm_response: str, output_parser: PydanticOutputParser) -> Any:
    """
    LLMレスポンスをPydanticモデルにパースします
    (レガシーコード互換用：新しいコードでは get_structured_llm を使用してください)
    
    Args:
        llm_response: LLMからのレスポンス
        output_parser: 出力パーサー
        
    Returns:
        パースされたPydanticモデル
    """
    try:
        return output_parser.parse(llm_response)
    except Exception as e:
        print(f"パースエラー: {e}")
        return None


# LLMプロンプトテンプレート

SCRIPT_ANALYSIS_SYSTEM_PROMPT = """
あなたはレガシーコードの解析と理解を専門とする上級ソフトウェアエンジニアです。
与えられたソースコードを詳細に分析し、以下の情報を抽出してください：

1. ファイルの目的と全体の要約
2. 実装されている主要な機能とその説明
3. 他のファイルやシステムとの依存関係
4. データ構造や重要な変数
5. ビジネスルールやロジック
6. 技術的負債や改善点

回答は客観的で詳細かつ正確であることが重要です。
特にレガシーシステムの文脈や業界固有の知識を活用して、コードの意図を把握してください。
"""

SCRIPT_ANALYSIS_HUMAN_PROMPT = """
以下のファイルを解析してください：

ファイルパス: {file_path}
ファイルタイプ: {file_type}

ソースコード:
```
{file_content}
```

JSON形式で回答してください：
```json
{{
  "file_path": "ファイルパス",
  "file_type": "ファイルタイプ",
  "summary": "ファイル全体の要約（200-300字）",
  "purpose": "ファイルの主な目的（100字以内）",
  "functions": [
    {{
      "name": "関数/プロシージャ名",
      "description": "機能の説明",
      "parameters": "パラメータ（あれば）",
      "return_value": "戻り値（あれば）"
    }}
  ],
  "dependencies": [
    "依存関係（ライブラリ、他のファイル、外部システムなど）"
  ],
  "data_structures": [
    {{
      "name": "データ構造名",
      "type": "型情報",
      "description": "説明"
    }}
  ],
  "business_rules": [
    "識別されたビジネスルール"
  ],
  "technical_debt": [
    "技術的負債や改善点"
  ]
}}
```
"""

GROUP_ANALYSIS_SYSTEM_PROMPT = """
あなたはレガシーシステムのリバースエンジニアリングを専門とする上級システムアナリストです。
ソースコードファイル群を機能やビジネスドメインに基づいて適切なグループに分類する必要があります。
既存のグループ情報が提供されている場合は、それらの定義を理解し、新しいファイルがどのグループに属するかを判断してください。
既存のグループに合致しない場合は、新しいグループを提案してください。

グループ化の基準：
1. 機能的な関連性（同じビジネス機能を実装するファイル群）
2. データの関連性（同じデータ構造を扱うファイル群）
3. アーキテクチャ上の関連性（システムの同じレイヤーに属するファイル群）
4. ビジネスドメインの関連性
"""

GROUP_ANALYSIS_HUMAN_PROMPT = """
以下のファイル解析結果を確認し、適切なグループに分類してください：

ファイル情報:
{file_analysis}

既存のグループ情報:
{existing_groups}

回答はJSON形式で、次のいずれかを選択してください：

1. 既存グループに属する場合:
```json
{{
  "group_id": "既存のグループID",
  "rationale": "このグループに分類した理由（100-200字）"
}}
```

2. 新しいグループが必要な場合:
```json
{{
  "group_id": "new",
  "group_name": "新しいグループ名（簡潔に）",
  "description": "グループの説明（100-200字）",
  "rationale": "新しいグループを作成した理由（100-200字）"
}}
```
"""

DOCUMENT_GENERATION_SYSTEM_PROMPT = """
あなたはレガシーシステムの仕様書を作成する技術ドキュメント専門家です。
与えられたコード解析情報から、エンジニアが理解しやすい詳細な技術仕様書を作成してください。

良い仕様書の条件：
1. 明確で簡潔な説明
2. 論理的な構成
3. 適切な見出しと階層構造
4. 技術的な正確さ
5. 実装詳細だけでなく、ビジネス目的や要件の説明

出力はMarkdown形式で、次のセクションを含めてください：
- 概要
- 主要機能
- アーキテクチャ/構成
- データフロー
- インターフェース定義
- ビジネスルール
- 制約条件
- 依存関係
"""

DOCUMENT_GENERATION_HUMAN_PROMPT = """
以下のグループに関する解析情報から、仕様書のセクションを作成してください：

グループ名: {group_name}
グループ説明: {group_description}

このグループに含まれるファイル:
{group_files}

Markdown形式で、詳細な仕様書セクションを作成してください。
タイトルは適切なものを選び、必要に応じてサブセクションを追加してください。
このセクションはシステム全体の仕様書の一部となります。
"""

CONSISTENCY_CHECK_SYSTEM_PROMPT = """
あなたはソフトウェアドキュメントの品質と整合性を検証する専門家です。
生成された技術仕様書のセクションをレビューし、以下の観点から評価してください：

評価基準：
1. 正確性: 技術的な誤りや矛盾がないか
2. 完全性: 必要な情報がすべて含まれているか
3. 一貫性: ドキュメント内で用語や概念が一貫して使用されているか
4. 明確性: 説明が明確で理解しやすいか
5. 構造: 論理的な構成になっているか

改善点や矛盾を発見した場合は、具体的なフィードバックを提供してください。
"""

CONSISTENCY_CHECK_HUMAN_PROMPT = """
以下のドキュメントセクションをレビューしてください：

セクションID: {section_id}
セクションタイトル: {section_title}

内容:
{section_content}

関連する他のセクションの情報（参考）:
{related_sections}

このセクションの整合性評価をJSON形式で回答してください：

```json
{{
  "section_id": "{section_id}",
  "is_consistent": true/false,
  "feedback": "改善や修正が必要な場合は、具体的なフィードバックを記載"
}}
```
"""

DOCUMENT_OUTLINE_SYSTEM_PROMPT = """
あなたはシステム仕様書の構成と設計を専門とする技術ドキュメント専門家です。
レガシーシステムの解析結果に基づいて、全体の仕様書のアウトライン（目次）を作成してください。

良い目次の条件：
1. 論理的な構成と流れ
2. 適切な見出しレベルと階層
3. システム全体を網羅する内容
4. 読者（エンジニア）にとって参照しやすい構成
5. ビジネス要件と技術実装の両方をカバー
"""

DOCUMENT_OUTLINE_HUMAN_PROMPT = """
以下のグループ情報に基づいて、全体的な仕様書のアウトライン（目次）を作成してください：

グループ情報:
{groups_info}

整合性チェックからのフィードバック:
{consistency_feedback}

JSON形式で回答してください：

```json
{{
  "title": "システム全体のタイトル",
  "introduction": "序論の概要（100-200字）",
  "sections": [
    {{
      "id": "セクションID",
      "title": "セクションタイトル",
      "description": "このセクションの概要（50-100字）",
      "subsections": [
        {{
          "id": "サブセクションID",
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

必ずシステム全体を論理的な流れで構成し、すべてのグループ情報が適切に配置されるようにしてください。
""" 