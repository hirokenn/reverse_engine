from fns_general import _get_tab_info_from_name
from fns_general import _gen_header_list
from fns_general import _header_li_to_df
from fns_kanseizumi import _merge_files_of_same_year, \
  _gen_linked_var_dict, _get_tabcol_info_from_textlst, _dic2data
import openpyxl
import pandas as pd
import numpy as np
import os
import re


# =============================================================================
# =============================================================================
# =============================================================================
# 統計表ファイルから変数名変遷表型のデータフレームを作成（Sheet1～Sheet4を作成）
# =============================================================================
# =============================================================================
# =============================================================================


# long形式の全年変数一覧を作成
# =============================================================================
def gen_df_varlist(xlsx_files, in_dir):
    '''
    ＜引数＞
    xlsx_files：統計表ファイルのリスト
    in_dir：統計表ファイルのディレクトリ, added by Chihiro

    ＜戻り値＞
    long形式のdataframe
    '''
    # 初期化
    df_out = None

    # 統計表Excelファイルの西暦を格納
    years = [_get_tab_info_from_name(file)[0] for file in xlsx_files]
    years = sorted(list(set(years)))

    for year in years:
        # 各ファイルから表頭を回収
        files = [file for file in xlsx_files
                 if _get_tab_info_from_name(file)[0] == year]

        for i, file in enumerate(files):
            # ファイルのフルパス
            # file = files[0]
            fullpath = f'{in_dir}/{file}'

            # 表頭を取得
            wb = openpyxl.load_workbook(fullpath)
            dt_start_row = int(wb['Metadata']['B1'].value)
            header_li = _gen_header_list(wb['MachineReady'], dt_start_row)

            # 統計表の情報を含めて、DataFrame化
            df = _header_li_to_df(header_li, file)
            df = df.rename(columns={'varid': 'col'})
            df['col'] = list(range(df.shape[0]))

            # df を df_all へ集約
            # df.append is deprecated. Use DataFrame.concat instead.
            if i == 0:
                df_out_t = df
            else:
                df_out_t = pd.concat([df_out_t, df], axis=0)
                
            # if i == 0:
            #     df_out_t = df
            # else:
            #     df_out_t = df_out_t.append(df, ignore_index=True)

        df_out = pd.concat([df_out, df_out_t], axis=0)

        # key_col の候補を追加しておく
        # df_out.loc[df_out.var_orig == '府県', 'key_col'] = 1
        df_out['key_col'] = None
        rep = df_out.var_orig.str.contains(r'府県|府懸|府縣', na=False)
        df_out.loc[rep, 'key_col'] = 1

    return df_out


# # %% sheet1を作成：統計表ファイルから辞書型のデータフレームを作成
# # 過年度の集計値との重複を使って，前年の変数と接続する
# # =============================================================================
# def gen_table_sheet1_old(in_dir, xlsx_files, key_col_dict, regex, tol=1):
#     '''
#     ＜引数＞
#     xlsx_files：統計表ファイルのリスト
#     na_cols, key_cols, regex：集計行の抽出条件
#     （na_cols：na_cols列のデータがnaの行を抽出，key_cols：key_cols列のデータがregexの行を抽出）
#     tol：集計データの非重複の許容度

#     ＜戻り値＞
#     sheet1型データ
#     '''
#     # 初期化
#     df_out = None
#     nolink = []

#     # 統計表Excelファイルの西暦を格納
#     years = [_get_tab_info_from_name(file)[0] for file in xlsx_files]
#     years = sorted(list(set(years)))

#     # 1年ごとに前年の統計表と経年接続する
#     # nonkey_cols = [na_cols, key_cols]
#     for year in years:
#         # year = 1937
#         print(f'\n')
#         print(f'Processing {year}')

#         # 1. 地方・府県列をkeyとして横結合（当該年で統計表が複数ある場合）
#         print(f'Merging files in year = {year}')
#         # t-1年
#         if year-1 >= min(years):
#             df1, ncol_lst1 = _merge_files_of_same_year(
#                 in_dir, xlsx_files, year-1, key_col_dict)

#         else:
#             df1 = None

#         # t年
#         df2, ncol_lst2 = _merge_files_of_same_year(
#             in_dir, xlsx_files, year, key_col_dict)

#         # 2. 経年接続の実行
#         if df1 is not None:
#             # 年次データの行のみ選択
#             # keycol は一番左 = 0 にある
#             df1 = df1[df1.iloc[:, 0].str.contains(regex, na=False)]
#             df2 = df2[df2.iloc[:, 0].str.contains(regex, na=False)]
# #             # 列indexを0始まりにリセット
# #             df1.columns = range(df1.shape[1])
# #             df2.columns = range(df2.shape[1])

#             # 経年接続した変数の辞書を取得
#             # print('columns', list(df1.columns), list(df2.columns))
#             # print('######################', df1, '####################', df2)

#             # 経年接続の実行
#             print(f'Linking variables between year {year} and {year-1}')
#             key_cols = [0]  # key列は1列のみ，かつ一番左に残しているので，決め打ちでよい
#             linked_vars = _gen_linked_var_dict(df1, df2, key_cols, tol)

#             if any(linked_vars):
#                 # key, valの各成分（列名）からタプル(year, tab_no, tab_subno, 列index)を生成
#                 tabcolinfo_df1 = _get_tabcol_info_from_textlst(
#                     list(linked_vars.keys()))
#                 tabcolinfo_df2 = _get_tabcol_info_from_textlst(
#                     list(linked_vars.values()))
# #                 tcol_keys = [tuple([tcol])+ tcol_keys[-1][:-1] if tcol in key else tcol for tcol in tcol_keys]
# #                 tcol_vals = [tuple([tcol])+ tcol_keys[-1][:-1] if tcol in key else tcol for tcol in tcol_vals]

#                 # print('tcol_keys', tcol_keys, tcol_vals)
#                 # ytcol_keys = [tuple([year-1]) + tcol
#                 #               for tcol in tcol_keys if tcol not in key]
#                 # ytcol_vals = [tuple([year]) + tcol
#                 #               for tcol in tcol_vals if tcol not in key]
#                 ytcol_df1 = [tuple([year-1]) + tcol for tcol in tabcolinfo_df1]
#                 ytcol_df2 = [tuple([year]) + tcol for tcol in tabcolinfo_df2]

#                 # # !!FIXME: 最終年の行を追加する？
#                 # if year+1 <= max(years):
#                 #     ytcol_df2 = [tuple([year+1]) + tcol for tcol in tabcolinfo_df2]
#                 # else:
#                 #     ytcol_df2 = [(None, None, None, None)
#                 #                 for i, l in enumerate(ytcol_df1)]

#                 # データフレームの作成
#                 df_temp = pd.concat([
#                     pd.DataFrame(ytcol_df1),
#                     pd.DataFrame(ytcol_df2)
#                 ], axis=1)

#                 # 列名をつける
#                 df_temp.columns = ['year1', 'tab_no1', 'tab_subno1', 'col1',
#                                    'year2', 'tab_no2', 'tab_subno2', 'col2']
#                 if df_out is None:
#                     df_out = df_temp.copy()
#                 else:
#                     df_out = pd.concat([df_out, df_temp])
#             # else:
#                 # 各年の列が結合できない
#                 # nolink.append([year-1, year])
#                 # print(year-1, year)
#                 # print(df1)
#                 # print(df2)

#     # 出力
#     if nolink:
#         return df_out
#     else:
#         print('=========結合列のないファイルがあります=========')
#         print(nolink)
#         return df_out


# %% sheet1を作成：統計表ファイルから辞書型のデータフレームを作成
# 過年度の集計値との重複を使って，前年の変数と接続する
# =============================================================================
def gen_table_sheet1(in_dir, xlsx_files, key_col_dict, regex, tol=1):
    '''
    ＜引数＞
    xlsx_files：統計表ファイルのリスト
    na_cols, key_cols, regex：集計行の抽出条件
    （na_cols：na_cols列のデータがnaの行を抽出，key_cols：key_cols列のデータがregexの行を抽出）
    tol：集計データの非重複の許容度

    ＜戻り値＞
    sheet1型データ
    '''
    # 初期化
    df_out = None
    nolink = []

    # 統計表Excelファイルの西暦を格納
    years = [_get_tab_info_from_name(file)[0] for file in xlsx_files]
    years = sorted(list(set(years)))

    # 1年ごとに前年の統計表と経年接続する
    # nonkey_cols = [na_cols, key_cols]
    for year in years:
        print(f'\n')
        print(f'Processing {year}')

        # 1. 地方・府県列をkeyとして横結合（当該年で統計表が複数ある場合）
        print(f'Merging files in year = {year}')
        # t年
        df1, ncol_lst1 = _merge_files_of_same_year(
            in_dir, xlsx_files, year, key_col_dict)

        # t+1年
        if year+1 <= max(years):
            df2, ncol_lst2 = _merge_files_of_same_year(
                in_dir, xlsx_files, year+1, key_col_dict)
        else:  # 最終+1年には便宜上初年度のデータを割当
            df2, ncol_lst2 = _merge_files_of_same_year(
                in_dir, xlsx_files, min(years), key_col_dict)

        # 2. 経年接続の実行
        # 年次データの行のみ選択
        # keycol は一番左 = 0 にある
        df1 = df1[df1.iloc[:, 0].str.contains(regex, na=False)]
        df2 = df2[df2.iloc[:, 0].str.contains(regex, na=False)]

        # 経年接続の実行
        print(f'Linking variables between year {year} and {year+1}')
        key_cols = [0]  # key列は1列のみ，かつ一番左に残しているので，決め打ちでよい
        linked_vars = _gen_linked_var_dict(df1, df2, key_cols, tol)

        if any(linked_vars):
            # key, valの各成分（列名）からタプル(year, tab_no, tab_subno, 列index)を生成
            tabcolinfo_df1 = _get_tabcol_info_from_textlst(
                list(linked_vars.keys()))
            tabcolinfo_df2 = _get_tabcol_info_from_textlst(
                list(linked_vars.values()))

            # yearと結合
            ytcol_df1 = [tuple([year]) + tcol for tcol in tabcolinfo_df1]

            if year+1 <= max(years):
                ytcol_df2 = [tuple([year+1]) + tcol for tcol in tabcolinfo_df2]
            else:
                ytcol_df2 = [(None, None, None, None)
                             for i, l in enumerate(ytcol_df1)]

            # データフレームの作成
            df_temp = pd.concat([
                pd.DataFrame(ytcol_df1),
                pd.DataFrame(ytcol_df2)
            ], axis=1)
            # print(df_temp)

            # 列名をつける
            df_temp.columns = ['year1', 'tab_no1', 'tab_subno1', 'col1',
                               'year2', 'tab_no2', 'tab_subno2', 'col2']
            
            if df_out is None:
                df_out = df_temp.copy()
            else:
                df_out = pd.concat([df_out, df_temp]) # The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.

    print(f'経年接続を終了し，df_outを出力しました．')
    return df_out


# %% 一貫変数名を与えたlong形式のdataframeを作成する
# =============================================================================
def gen_consvar_df_l(df):

    # 1. 経年一貫変数を与える
    # gen_tabe_sheet2(df) より ------
    df_temp = df.copy()
    keys = df_temp[['year1', 'tab_no1', 'tab_subno1', 'col1']].values.tolist()
    values = df_temp[['year2', 'tab_no2',
                      'tab_subno2', 'col2']].values.tolist()
    keys = [tuple(k) for k in keys]
    values = [tuple(v) for v in values]
    dic = dict(zip(keys, values))

    # 辞書からデータフレームを作成
    df_out = _dic2data(dic, None)
    # gen_tabe_sheet2(df) より ------

    # 2. Long形式へ変換
    # reshape long consvar@, i(year tab_no tab_subno) j(consvarid)
    # https://lost-stats.github.io/Data_Manipulation/Reshaping/reshape_panel_data_from_wide_to_long.html
    # df_out
    df_out = df_out.reset_index(drop=True)
    df_out['id'] = df_out.index
    df_out = df_out.astype('Int64')  # float -> int に変換（NaNを許容するint）

    # long形式に変換
    df_l = pd.wide_to_long(df_out, ['consvar'], i='id', j='consvarid')
    df_l = df_l.rename(columns={'consvar': 'col'})
    df_l['tabcol'] = 't' + df_l['tab_no'].astype(str) \
        + '_' + df_l['tab_subno'].astype(str) \
        + '_c' + df_l['col'].astype(str)
    # colが欠損の行を落とす
    df_l = df_l[df_l['col'].notna()]
    df_l = df_l.reset_index()
    df_l = df_l[['id', 'year', 'tab_no',
                'tab_subno', 'col', 'tabcol', 'consvarid']]
    # df_l

    return df_l


# %% wide形式の変数名変遷表を出力する
# def: gen_consvar_table(df_l, value = 'varname'):
# 引数は，df (df_w) と value = tabcol / varname
# Sheet3: 表体の値が，列indexベース
# Sheet4: 表体の値が，変数名（var_orig）ベース（ただし，表番号等の修飾がつく）
# df_out3 = gen_consvar_table(df_l, value = 'tabcol')
# df_out4 = gen_consvar_table(df_l, value = 'varname')
# =============================================================================
def gen_consvar_table(df_l, df_varlist, value='varname'):
    '''
    ＜引数＞
    df_l：sheet2型データフレーム
    value: 変数名なし('tabcol') あり('varname')
    ＜戻り値＞
    df_out：value形式のデータフレーム
    '''
    # 形式選択
    if value == 'tabcol':
        df_tmp = df_l[['consvarid', 'year', 'tabcol']]
    elif value == 'varname':
        # df_l に var_orig をくっつける．
        df_tmp = pd.merge(df_l,
                          df_varlist.rename(
                              columns={'tab_num': 'tab_no', 'tab_subnum': 'tab_subno'}),
                          on=['year', 'tab_no', 'tab_subno', 'col'], how='inner')
        df_tmp['colvar'] = df_tmp['tabcol']+'_'+df_tmp['var_orig']
        df_tmp = df_tmp[['consvarid', 'year', 'colvar']]
    else:
        print(f'{value}という形式はありません．')

    # 3. row=year, col=consvar*, value=tabcol のWide形式に(Sheet3の出力)
    # https://pandas.pydata.org/pandas-docs/stable/user_guide/reshaping.html#reshaping-stacking
    df_tmp = df_tmp.set_index(['year', 'consvarid'])
    df_tmp
    df_w = df_tmp.unstack(1)

    # カラム名を year, consvar1 consvar2... に修正する
    df_w.columns = ['consvar'+str(col[1]) for col in df_w.columns]
    df_w = df_w.reset_index()
    df_w

    print(f'変数名変遷表を作成しました．')
    return df_w


# %% 変数名変遷表のExcelファイルを作成する
# =============================================================================
def gen_varchange_fl(df_var_l, df_out4, varchange_fl):

    # ファイルの存在チェック：
    if os.path.isfile(varchange_fl):
        raise Exception(f'{varchange_fl} は既に作成されています！')
    else:

        # key_colに変数名 var_orig をつける
        df_var_l['var_orig_full'] = 't' + df_var_l['tab_num'].astype('str') \
            + '_'+df_var_l['tab_subnum'].astype('str')+'_c' \
            + df_var_l['col'].astype('str') + '_' + df_var_l['var_orig']

        # engineとしてxlsxwriterを使う
        writer = pd.ExcelWriter(varchange_fl, engine='xlsxwriter')

        df_out4.to_excel(writer, sheet_name="変数名変遷表_提案")
        df_out4.to_excel(writer, sheet_name="変数名変遷表_確定")

        df_var_l.to_excel(writer, sheet_name='変数名変換表', index=False)
        wb = writer.book
        ws = writer.sheets['変数名変換表']

        df_out5 = df_out4.reset_index()

        for i in range(df_var_l.shape[0]):
            year = df_var_l['year'][i]
            # excelファイル[変数名変遷表_確定]シート上の year年の行
            row_year = df_out5['year'][df_out5['year'] == year].index[0] + 2

            # 変数名変遷表 から値を反映するための関数の埋め込み
            # print(f'=@INDIRECT(ADDRESS(1,MATCH(H{i+1}, 変数名変遷表_確定!{row_year}:{row_year},0),,,"変数名変遷表_確定"))')
            ws.write_formula(i+1, 8,
                             f'=@INDIRECT(ADDRESS(1,MATCH(H{i+2}, 変数名変遷表_確定!{row_year}:{row_year},0),,,"変数名変遷表_確定"))')

        # 表頭の設定
        hd_format = wb.add_format()
        hd_format.set_bold()
        hd_format.set_align('center')
        ws.write(0, 8, 'var_cons', hd_format)
        # 列幅の設定
        col_format = wb.add_format()
        col_format.set_align('right')
        ws.set_column(0, 1, 8)
        ws.set_column(2, 2, 10)
        ws.set_column(3, 3, 8)
        ws.set_column(4, 4, 40)
        ws.set_column(5, 5, 15)
        ws.set_column(6, 6, 10)
        ws.set_column(7, 7, 60)
        ws.set_column(8, 8, 20)
        # ウィンドウ枠の分割
        ws.freeze_panes('A2')
        # オートフィルタの設定
        ws.autofilter('A1:I1')

        writer.close()


# %% パネルデータを作成する関数
# =============================================================================
def gen_panel_data(in_dir, xlsx_files, varchange_fl, vartab_sh):
    '''
    パネルデータを生成する．

    Args:
        xlsx_files: 各年データのExcelファイルのリスト
        varchange_fl: 変数名変換表が入ったファイルのパス
        vartab_sheet: 変数名変換表のシート名

    Returns:
        df_out: 連結してパネルデータ化したデータフレーム

    '''
    # 0. 出力の初期化
    df_panel = None

    # 統計表Excelファイルの西暦を格納
    years = [_get_tab_info_from_name(file)[0] for file in xlsx_files]
    years = sorted(list(set(years)))

    # 1. 変数名変換表を読み込む
    df_l = pd.read_excel(varchange_fl, sheet_name=vartab_sh, header=0)

    # 必ず「変数名変遷表」を一度Excelで開いて保存すること
    # そうしないと var_cons の数式を評価した状態でxlsxファイルを読み込めない：
    # https://note.com/vanaya/n/nd46b4b7fc55e
    if df_l['var_cons'].dtype == np.int64:
        raise Exception(
            f'var_consが取得できません．一度，{varchange_fl}をExcelで開いて保存してください．')

    else:
        df_l['var_orig_tabcol'] = df_l['var_orig_full'].apply(
            lambda x: re.search(r't[0-9]+_[0-9]+_c[0-9]+', x).group() if x else None)
        # df_l = df_l.dropna(subset=['var_cons'])

        # key_col_dict を取得
        df_key_col = df_l[['file', 'col', 'key_col']]
        df_key_col = df_key_col.dropna(how='any')
        key_col_dict = dict(zip(df_key_col['file'], df_key_col['col']))

        for year in years:
            # year = 1905
            # 1. 地方・府県列をkeyとして横結合（当該年で統計表が複数ある場合）
            print(f'Merging files in year = {year}')
            df_t, ncol_t = _merge_files_of_same_year(
                in_dir, xlsx_files, year, key_col_dict)

            # 2. 列名をvarconsに置換する．
            # まず，df_l['var_orig_tabcol'] = 't122_1_c4' のような列を
            # df_l['var_orig_full'] から作る
            # 該当年のvar_orig_tabcolとvar_consを抽出
            var_orig_tabcol = list(
                df_l[df_l['year'] == year]['var_orig_tabcol'])
            var_cons = list(df_l[df_l['year'] == year]['var_cons'])
            # 次に，df_l['var_orig_tabcol'] と df_l['var_cons'] の対応関係から,
            # df_t.columns を置換する
            df_t = df_t.rename(columns=dict(zip(var_orig_tabcol, var_cons)))

            # 3. yearを追加する
            df_t['year'] = year
            df_year = df_t.pop('year')
            df_t.insert(0, 'year', df_year)

            # 3. 前年までのdf_t と縦結合する
            df_panel = pd.concat(
                [df_panel, df_t], ignore_index=True).reset_index(drop=True)
            # print(df_panel)

    print(f'Generated panel data!')
    return df_panel
