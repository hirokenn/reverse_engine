from typing import Dict, List, Any
import json
import os

from src.utils.file_utils import is_sensitive_file
from src.utils.config import load_config
from src.utils.llm_utils import get_llm, get_structured_llm
from pydantic import BaseModel, Field


class ScriptAnalysisResult(BaseModel):
    """スクリプト解析結果のスキーマ"""
    detailed_analysis: str = Field(description="スクリプトの詳細な説明。役割、主な機能、実装の詳細、他のコンポーネントとの関係などについて包括的に説明")
    summary: str = Field(description="スクリプトの簡潔な要約（100文字以内）")


class ScriptAnalysisNode:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.llm = get_llm()
        
    def process(self, scripts):
        """
        複数のスクリプトを処理し、詳細な説明・簡潔な要約とベクトルストアへの格納を行う
        
        Args:
            scripts: 処理対象のスクリプトリスト
            
        Returns:
            スクリプト要約のリスト
        """
        summaries = []
        analysis_results = []
        
        for script in scripts:
            # スクリプトの詳細な説明と簡潔な要約を生成
            analysis_result = self.process_single_script(script)
            
            if isinstance(analysis_result, tuple) and len(analysis_result) == 2:
                # エラー処理の場合（tuple形式で返される）
                detailed_analysis, brief_summary = analysis_result
            else:
                # 正常処理の場合（ScriptAnalysisResult形式で返される）
                detailed_analysis = analysis_result.detailed_analysis
                brief_summary = analysis_result.summary
            
            # 解析結果を格納
            result_dict = {
                "file_path": script["file_path"],
                "file_type": script.get("file_type", "unknown"),
                "detailed_analysis": detailed_analysis,  # 詳細な説明
                "summary": brief_summary,  # 簡潔な要約
                "purpose": "スクリプトの目的",
                "functions": [],
                "dependencies": [],
                "data_structures": [],
                "business_rules": []
            }
            
            analysis_results.append(result_dict)
            
            summaries.append({
                "script_id": script["file_path"],
                "detailed_analysis": detailed_analysis,
                "summary": brief_summary,
                "content": script["content"]
            })
        
        # ベクトルストアには詳細な説明のみを格納
        if analysis_results:
            self.vector_store.add_analysis_results(analysis_results)
            
        return summaries
    
    def process_single_script(self, script):
        """
        単一のスクリプトを処理し、詳細な説明と簡潔な要約を生成する
        
        Args:
            script: 処理対象のスクリプト（辞書形式）
            
        Returns:
            ScriptAnalysisResult オブジェクト、または (詳細な説明, 簡潔な要約) のタプル
        """
        try:
            # センシティブファイルのチェック
            config = load_config()
            if is_sensitive_file(script["file_path"], config):
                print(f"センシティブファイルをスキップします: {script['file_path']}")
                return "センシティブファイルのため解析をスキップしました", "センシティブファイル"
            
            # 構造化出力用にLLMを設定
            structured_llm = get_structured_llm(ScriptAnalysisResult)
            
            # LLMを使用してスクリプトの解析を生成（詳細と要約を一度に）
            prompt = f"""
            以下のスクリプトを解析し、詳細な説明と簡潔な要約の両方を作成してください。
            
            詳細な説明には、このスクリプトの役割、主な機能、実装の詳細、他のコンポーネントとの関係などについて
            包括的に説明してください。
            
            簡潔な要約は100文字以内で、このスクリプトの役割や主な機能を端的に説明してください。
            
            ファイルパス: {script["file_path"]}
            ファイルタイプ: {script.get("file_type", "unknown")}
            
            内容:
            {script["content"][:4000]}  # コンテンツが長い場合は一部のみを使用
            """
            
            # プロンプトを表示
            print("\n===== スクリプト解析 プロンプト =====")
            print(f"ファイルパス: {script['file_path']}")
            print(prompt[:300] + "..." if len(prompt) > 300 else prompt)
            print("===== スクリプト解析 プロンプト終了 =====\n")
            
            # 構造化出力でLLMを呼び出し
            response = structured_llm.invoke(prompt)
            return response
            
        except Exception as e:
            print(f"スクリプト {script['file_path']} の処理中にエラーが発生しました: {str(e)}")
            return f"エラー: {str(e)}", f"エラー: {str(e)}" 