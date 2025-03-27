from pathlib import Path
import os
import pprint
import pandas as pd

# =============================================================================
# =============================================================================
# %% 汎用関数
# =============================================================================
# =============================================================================


# %% ファイル一覧を作成する
# ======================================================================
def gen_file_list(dir, file_regex, show=False):
    '''
    ディレクトリから画像ファイルのリストを取得する

    args:
        img_dir: 画像ファイルがあるディレクトリ（フルパス）
        file_regex: 画像ファイル名の正規表現
        show: {True, False} ファイルのリストを表示するか
    '''

    files = [os.path.basename(p) for p in Path(dir).glob(file_regex)
             if os.path.isfile(p)]

    if show:
        pprint.pprint(files)

    return sorted(files)


# %% データファイルの一部を表示する
# ======================================================================
def show_data_file(in_dir, xlsx_files):
    for i, file in enumerate(xlsx_files):
        print(f'\n{file}')
        df = _get_machineready_data(f'{in_dir}/{file}')
        df = df.iloc[0:10, 0:4]
        print(df)


# %% ファイル名から 年、表番号、補足表番号（ある場合）を生成して返す。
# ================================================================
def _get_tab_info_from_name(file_name):

    # ファイル名を取得
    tab_id = file_name.replace('.xlsx', '')

    # ファイル名の先頭から、年（year）と表番号（tab_num）を取得
    temp_list = tab_id.split('_')
    year = int(temp_list[0])
    tab_no = int(temp_list[1].replace('t', ''))

    # 補足表がある場合、その番号を取得
    if len(temp_list) > 2 and temp_list[2].isnumeric():
        tab_subno = int(temp_list[2])
    else:
        tab_subno = 0

    return year, tab_no, tab_subno

# # test
# _get_tab_info_from_name('1911_t007_01.xlsx')


# %% 統計表Excelファイルから，MachineReadyなデータ（シート）を読み込む関数
# =============================================================================
def _get_machineready_data(xlsx_file):

    # Metaデータシートから各種情報を取得
    metadata = pd.read_excel(xlsx_file, sheet_name='Metadata', header=None)
    data_start_row = metadata[1][metadata[0] == 'data_start_row'].values
    data_start_row = int(data_start_row) if data_start_row else int(
        metadata[1][metadata[0] == 'data_cellrange'].values)

    # MachineReadyシートからデータ部分を取得
    df = pd.read_excel(xlsx_file, sheet_name='MachineReady', header=None,
                       skiprows=data_start_row-1)

    return df


# %%  rng 内に値の入ったセルがある -> True
# ================================================================
def _is_blank_range(rng):

    for cell in rng:
        if cell.value != None:
            return False

    return True


# %%  表頭の値を '_' で連結し、シート内のすべての表頭のリストを生成
# ================================================================
def _gen_header_list(ws, st_row):

    header_li = []

    for col in ws.iter_cols():

        # 空列ならスキップ
        if _is_blank_range(col):
            continue

        # 表頭用リスト
        header = []

        # 表頭（data_start_row の手前まで）の値を回収
        for cell in col:
            if cell.row < st_row and cell.value != None:
                header.append(cell.value)

        # '_'で接続して、append
        header_li.append('_'.join(header))

    return header_li


# %%  表頭のリストに年、表番号、補足表番号を付与して DataFrame 形式に変換する
# ================================================================
def _header_li_to_df(header_li, file):

    # header_li を DataFrame 形式に変換し、'var_orig' とする
    df = pd.DataFrame(data=header_li, columns=['var_orig'])

    # ファイル名から年、表番号、補足表番号を辞書形式で取得
    year, tab_no, tab_subno = _get_tab_info_from_name(file)

    # df に dic から情報追加
    df['year'] = year
    df['tab_num'] = tab_no
    df['tab_subnum'] = tab_subno
    df['file'] = file

    # df の並び替えを行う
    df = df.reindex(columns=['year', 'tab_num',
                             'tab_subnum', 'varid', 'var_orig', 'file'])

    return df
