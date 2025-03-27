from typing import Dict, List, Any
import json
import os

from src.utils.file_utils import is_sensitive_file
from src.utils.config import load_config
from src.utils.llm_utils import get_llm


class ScriptAnalysisNode:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.llm = get_llm()
        
    def process(self, scripts):
        """
        複数のスクリプトを処理し、要約とベクトルストアへの格納を行う
        
        Args:
            scripts: 処理対象のスクリプトリスト
            
        Returns:
            スクリプト要約のリスト
        """
        summaries = []
        analysis_results = []
        
        for script in scripts:
            # スクリプトの要約を生成
            summary = self.process_single_script(script)
            
            # 解析結果を格納
            analysis_result = {
                "file_path": script["file_path"],
                "file_type": script.get("file_type", "unknown"),
                "summary": summary,
                "purpose": "スクリプトの目的",
                "functions": [],
                "dependencies": [],
                "data_structures": [],
                "business_rules": []
            }
            
            analysis_results.append(analysis_result)
            
            summaries.append({
                "script_id": script["file_path"],
                "summary": summary,
                "content": script["content"]
            })
        
        # ベクトルストアに一括で追加
        if analysis_results:
            self.vector_store.add_analysis_results(analysis_results)
            
        return summaries
    
    def process_single_script(self, script):
        """
        単一のスクリプトを処理し、要約を生成する
        
        Args:
            script: 処理対象のスクリプト（辞書形式）
            
        Returns:
            スクリプトの要約
        """
        try:
            # センシティブファイルのチェック
            config = load_config()
            if is_sensitive_file(script["file_path"], config):
                print(f"センシティブファイルをスキップします: {script['file_path']}")
                return "センシティブファイルのため解析をスキップしました"
                
            # LLMを使用してスクリプトの要約を生成
            prompt = f"""
            以下のスクリプトの要約を作成してください。
            このスクリプトの役割や主な機能について説明してください。
            
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
            
            response = self.llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"スクリプト {script['file_path']} の処理中にエラーが発生しました: {str(e)}")
            return f"エラー: {str(e)}" 