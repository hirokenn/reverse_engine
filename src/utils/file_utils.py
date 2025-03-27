import os
import glob
from typing import List, Dict, Any, Optional
import json
import markdown
from pathlib import Path
import mimetypes
import fnmatch
import re
import subprocess
import tempfile
import shutil


def get_file_list(directory_path: str, extensions: List[str] = None, config: Optional[dict] = None) -> List[str]:
    """
    指定されたディレクトリ内のファイル一覧を取得します。
    
    Args:
        directory_path: 検索対象のディレクトリパス
        extensions: 対象ファイル拡張子のリスト (例: ['.cbl', '.cobol'])
        config: 設定パラメータ（センシティブファイルの除外に使用）
    
    Returns:
        ファイルパスのリスト
    """
    all_files = []
    
    if not os.path.exists(directory_path):
        return all_files
    
    if extensions:
        for ext in extensions:
            pattern = os.path.join(directory_path, f"**/*{ext}")
            all_files.extend(glob.glob(pattern, recursive=True))
    else:
        pattern = os.path.join(directory_path, "**/*")
        all_files = [f for f in glob.glob(pattern, recursive=True) if os.path.isfile(f)]
    
    filtered_files = []
    for file in all_files:
        if config and is_sensitive_file(file, config):
            print(f"センシティブファイルをスキップします: {file}")
            continue
        filtered_files.append(file)
    
    return filtered_files


def read_file_content(file_path: str) -> str:
    """
    ファイルの内容を読み込みます。
    
    Args:
        file_path: ファイルパス
    
    Returns:
        ファイルの内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"ファイル読み込みエラー ({file_path}): {e}")
        return ""


def get_file_type(file_path: str) -> str:
    """
    ファイルの種類を判定します。
    
    Args:
        file_path: ファイルパス
    
    Returns:
        ファイルタイプの文字列
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    # 一般的なファイル拡張子とタイプのマッピング
    file_types = {
        '.cbl': 'COBOL',
        '.cob': 'COBOL',
        '.cobol': 'COBOL',
        '.jcl': 'JCL',
        '.java': 'Java',
        '.js': 'JavaScript',
        '.py': 'Python',
        '.c': 'C',
        '.cpp': 'C++',
        '.cs': 'C#',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.sql': 'SQL',
        '.xml': 'XML',
        '.html': 'HTML',
        '.css': 'CSS',
        '.json': 'JSON',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.md': 'Markdown',
        '.txt': 'Text',
    }
    
    return file_types.get(ext, f"Unknown ({ext})")


def save_json(data: Dict[str, Any], file_path: str) -> None:
    """
    JSONデータをファイルに保存します。
    
    Args:
        data: 保存するデータ
        file_path: 保存先ファイルパス
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_markdown(content: str, file_path: str) -> None:
    """
    Markdownコンテンツをファイルに保存します。
    
    Args:
        content: Markdownコンテンツ
        file_path: 保存先ファイルパス
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def markdown_to_html(markdown_content: str, output_path: str) -> None:
    """
    MarkdownコンテンツをHTMLに変換して保存します。
    
    Args:
        markdown_content: Markdownコンテンツ
        output_path: 保存先ファイルパス
    """
    html = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>レガシーシステム仕様書</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; max-width: 1200px; margin: 0 auto; }}
            h1, h2, h3 {{ color: #333; }}
            code {{ background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
            pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    """
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_template)


def markdown_to_pdf(markdown_files: List[str], output_pdf_path: str) -> None:
    """
    複数のMarkdownファイルを統合してPDFに変換します。
    
    Args:
        markdown_files: Markdownファイルパスのリスト
        output_pdf_path: 出力PDFファイルパス
    """
    try:
        # pandocがインストールされているか確認
        subprocess.run(["pandoc", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("pandocがインストールされていません。インストールしてください。")
        print("例: brew install pandoc (macOS) / apt-get install pandoc (Ubuntu)")
        print("また、PDFの生成にはLaTeXも必要です: brew install basictex (macOS) / apt-get install texlive-latex-base (Ubuntu)")
        return
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        # 統合用の一時Markdownファイル
        combined_md_path = os.path.join(temp_dir, "combined.md")
        
        # すべてのMarkdownファイルの内容を結合
        with open(combined_md_path, 'w', encoding='utf-8') as combined_file:
            for md_file in markdown_files:
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        combined_file.write(content)
                        combined_file.write("\n\n\\pagebreak\n\n")  # 各ファイルの後にページ区切りを追加
                except Exception as e:
                    print(f"ファイル {md_file} の読み込み中にエラーが発生しました: {str(e)}")
        
        # PDFに変換
        try:
            cmd = [
                "pandoc",
                combined_md_path,
                "-o", output_pdf_path,
                "--pdf-engine=xelatex",
                "-V", "geometry:margin=1in",
                "-V", "mainfont:IPAexGothic",
                "-V", "documentclass=report",
                "-V", "papersize=a4",
                "--toc"  # 目次を追加
            ]
            
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"PDFが正常に生成されました: {output_pdf_path}")
            
        except subprocess.CalledProcessError as e:
            print(f"PDFの生成中にエラーが発生しました: {e.stderr.decode('utf-8')}")
            
            # 代替手段としてHTMLを経由してPDFを生成
            try:
                # HTMLに変換
                html_path = os.path.join(temp_dir, "combined.html")
                with open(combined_md_path, 'r', encoding='utf-8') as md_file:
                    html_content = markdown.markdown(md_file.read(), extensions=['tables', 'fenced_code'])
                
                html_template = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>システム仕様書</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; max-width: 1200px; margin: 0 auto; }}
                        h1, h2, h3 {{ color: #333; }}
                        code {{ background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
                        pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                        table {{ border-collapse: collapse; width: 100%; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; }}
                        th {{ background-color: #f2f2f2; }}
                        tr:nth-child(even) {{ background-color: #f9f9f9; }}
                        @page {{ size: A4; margin: 2cm; }}
                        @media print {{ body {{ max-width: none; margin: 0; }} }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_template)
                
                # HTMLからPDFへの変換を試みる（wkhtmltopdfを使用）
                try:
                    subprocess.run(["wkhtmltopdf", html_path, output_pdf_path], check=True)
                    print(f"PDFが代替手段で生成されました: {output_pdf_path}")
                except (subprocess.SubprocessError, FileNotFoundError):
                    print("wkhtmltopdfがインストールされていないため、HTMLをコピーします")
                    # 代わりにHTMLファイルを出力
                    html_output_path = os.path.splitext(output_pdf_path)[0] + ".html"
                    shutil.copy(html_path, html_output_path)
                    print(f"HTMLファイルが生成されました: {html_output_path}")
            
            except Exception as html_error:
                print(f"代替手段での変換中にエラーが発生しました: {str(html_error)}")
                # 最後の手段としてマークダウンファイルをコピー
                md_output_path = os.path.splitext(output_pdf_path)[0] + ".md"
                shutil.copy(combined_md_path, md_output_path)
                print(f"マークダウンファイルが生成されました: {md_output_path}")


def is_sensitive_file(file_path: str, config: dict) -> bool:
    """
    ファイルがセンシティブかどうかを判定する
    
    Args:
        file_path: ファイルパス
        config: 設定パラメータ
    
    Returns:
        bool: センシティブな場合はTrue
    """
    # ファイル名パターンのチェック
    file_name = os.path.basename(file_path)
    for pattern in config.get("sensitive_patterns", []):
        if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
            return True
    
    # ファイル内容のチェック
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern in config.get("sensitive_content_patterns", []):
                if re.search(pattern, content, re.IGNORECASE):
                    return True
    except Exception:
        # ファイルが読めない場合は安全のためセンシティブとみなす
        return True
    
    return False 