"""
設定ファイルの読み込みと管理を行うモジュール
このモジュールは設定情報の読み込み、デフォルト値の提供、環境変数との連携を担当します。
"""
import os
import yaml
from typing import Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path


def load_config(config_path: str = "config.yml") -> Dict[str, Any]:
    """
    設定ファイルを読み込む
    
    YAMLファイルから設定を読み込み、デフォルト値とマージします。
    ファイルが存在しない場合や読み込みエラーの場合はデフォルト設定を使用します。
    
    Args:
        config_path: 設定ファイルのパス
    
    Returns:
        設定パラメータの辞書
    """
    # デフォルト設定値の定義
    default_config = {
        "legacy_code_path": "./source_code",  # レガシーコードの格納パス
        "output_dir": "./output",  # 出力ディレクトリ
        "chroma_db_path": "./chroma_db",  # ベクトルDBのパス
        "llm": {
            "model": "gpt-4",  # 使用するLLMモデル
            "temperature": 0.0,  # 生成の多様性（低いほど決定的）
            "max_tokens": 2000  # 生成する最大トークン数
        },
        "consistency_check": {
            "max_rejections": 3,  # 否定の最大回数
            "rejection_threshold": 0.7,  # 否定を行う閾値（0.0-1.0）
            "required_detail_level": "high",  # フィードバックの詳細度（low, medium, high）
            "focus_areas": [  # フィードバックの重点領域
                "technical_accuracy",  # 技術的正確性
                "completeness",  # 完全性
                "clarity",  # 明確性
                "business_logic",  # ビジネスロジック
                "code_coverage"  # コードカバレッジ
            ]
        },
        "sensitive_patterns": [  # センシティブファイルのパターン
            "*.env",  # 環境変数ファイル
            "*.env.*",  # 環境変数ファイルのバリエーション
            "config*.yml",  # 設定ファイル
            "config*.yaml",  # 設定ファイル
            "secrets*.yml",  # シークレットファイル
            "secrets*.yaml",  # シークレットファイル
            "*password*",  # パスワード関連
            "*secret*",  # シークレット関連
            "*key*",  # キー関連
            "*credential*",  # 認証情報関連
            "*.pem",  # 証明書/鍵ファイル
            "*.key",  # 鍵ファイル
            "*.crt",  # 証明書
            "*.cer",  # 証明書
            "*.p12",  # PKCS#12証明書
            "*.pfx"  # PFX証明書
        ],
        "sensitive_content_patterns": [  # センシティブな内容のパターン
            "API_KEY",  # APIキー
            "SECRET_KEY",  # シークレットキー
            "PASSWORD",  # パスワード
            "CREDENTIAL",  # 認証情報
            "ACCESS_TOKEN",  # アクセストークン
            "PRIVATE_KEY",  # 秘密鍵
            "-----BEGIN"  # 鍵や証明書の開始マーカー
        ]
    }
    
    try:
        # 設定ファイルが存在する場合は読み込む
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # ユーザー設定をデフォルト設定にマージ
                    _deep_merge(default_config, user_config)
    except Exception as e:
        print(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
        print("デフォルト設定を使用します。")
    
    return default_config


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> None:
    """
    2つの辞書を再帰的にマージする
    
    既存の辞書（base）と新しい辞書（update）をマージします。
    更新対象のキーが辞書の場合は、さらに再帰的にマージします。
    
    Args:
        base: ベースとなる辞書（上書きされる側）
        update: 更新する辞書（上書きする側）
    """
    for key, value in update.items():
        # キーが両方の辞書に存在し、両方が辞書型の場合は再帰的にマージ
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            # それ以外の場合は単純に上書き
            base[key] = value


def load_config_from_env():
    """
    .envファイルから環境変数を読み込む
    
    環境変数から設定を読み込み、必須項目の確認を行います。
    パスの絶対パス変換や必要なディレクトリの作成も行います。
    
    Returns:
        Dict[str, Any]: 環境変数から読み込んだ設定
    """
    # .envファイルから環境変数を読み込む
    load_dotenv()
    
    # 必須の環境変数
    required_vars = [
        "OPENAI_API_KEY",  # OpenAI APIキー
    ]
    
    # 環境変数の存在確認
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"必須の環境変数が設定されていません: {', '.join(missing_vars)}")
    
    # 設定の構築
    config = {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),  # OpenAI APIキー
        "chroma_db_path": os.getenv("CHROMA_DB_PATH", "./data/chroma_db"),  # ベクトルDBのパス
        "legacy_code_path": os.getenv("LEGACY_CODE_PATH", "./data/sample_legacy_code"),  # レガシーコードのパス
        "output_dir": os.getenv("OUTPUT_DIR", "./output"),  # 出力ディレクトリ
        "llm_model": os.getenv("LLM_MODEL", "gpt-4"),  # 使用するLLMモデル
    }
    
    # パスを絶対パスに変換
    for key in ["chroma_db_path", "legacy_code_path", "output_dir"]:
        config[key] = str(Path(config[key]).resolve())
        
        # ディレクトリの存在確認と作成
        os.makedirs(config[key], exist_ok=True)
    
    return config 