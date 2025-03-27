"""
パネルデータを作成するプロセスのrunファイル

1. 校正済み・公開用の統計表ファイルを整備しておく．
# -*- coding: utf-8 -*-
2．パネル化に必要な統計表ファイルを選定し，__MetaInputLog.xlsx の apply 列 にフラグ（1） を立てる．
3. 0_変数名一覧.xlsx ファイルを生成する
4. 0_変数名一覧.xlsx の変数名変遷表を編集し，変数を経年的に接続（リンク）する
5. gen_panerdata.py を実行し，パネルデータファイルを生成する．

"""

# %% import
# =============================================================
from concurrent.futures.process import _chain_from_iterable_of_lists
import pprint
import re
import os
from matplotlib.pyplot import show
import pandas as pd
import numpy as np
import math
from pandas.errors import MergeError
from pandas.errors import InvalidIndexError
import subprocess
from pathlib import Path
from pyparsing import col
import xlsxwriter
import openpyxl

import sys

# =============================================================================
# =============================================================================
# %% 汎用関数
# =============================================================================
# =============================================================================
directory_Panelize = 'Panelize'
sys.path.append(directory_Panelize)

from fns_general import gen_file_list
from fns_general import show_data_file
from fns_general import _get_tab_info_from_name
from fns_general import _get_machineready_data
from fns_general import _is_blank_range
from fns_general import _gen_header_list
from fns_general import _header_li_to_df


# =============================================================================
# =============================================================================
# 完成済み関数
# =============================================================================
# =============================================================================

from fns_kanseizumi import _merge_files_of_same_year
from fns_kanseizumi import _gen_linked_var_dict
from fns_kanseizumi import _get_tabcol_info_from_textlst
from fns_kanseizumi import _dic2list_onkey
from fns_kanseizumi import _dic2data

# =============================================================================
# =============================================================================
# =============================================================================
# 統計表ファイルから変数名変遷表型のデータフレームを作成（Sheet1～Sheet4を作成）
# =============================================================================
# =============================================================================
# =============================================================================

from fns_var_transition import gen_df_varlist
from fns_var_transition import gen_table_sheet1
from fns_var_transition import gen_consvar_df_l
from fns_var_transition import gen_consvar_table
from fns_var_transition import gen_varchange_fl
from fns_var_transition import gen_panel_data


# =============================================================================
# =============================================================================
# =============================================================================
# 年次ごとの総計表から変数を経年接続する
# =============================================================================
# =============================================================================
# %% ディレクトリの設定
# ================================================================

username = os.environ['USER']
# username = os.environ['USERNAME'] # This returned KeyError on Chihiro's Mac

if username == 'arimotoy':
    root_dir = f'g:/マイドライブ/Public/Panelize'
    # root_dir = 'o:/マイドライブ/TeikokuTokei'
else:
    root_dir = os.path.join(os.getcwd(), 'Panelize')


# %% Generic Params
# =========================================================
na_cols = 0
key_cols = 1
regex = r'(?:明治|大正|昭和)'
tol = 1


# %% Run: 
# 3つのファイルを作成する：
# 1. {field}_変数接続情報.xlsx: 変数接続の情報を集約したファイル
# 　・全年変数一覧l（long形式）
# 　・経年接続対応表: t年とt-1年の接続情報
# 　・変数名変遷表_提案：経年一貫変数を列，年を行に，wide形式にした表
#
# 2. {field}_key_col.xlsx： key_colフラグを手動で立てるためのファイル
# 　・key_col 列に，key_col候補のフラグを立ててあるが，手動で修正する
#
# 3. {field}_変数名変遷表.xlsx：変数名変遷表を手動修正し，変数名変換表を自動作成
# 　・変数名変遷表_提案：機械的に提案
# 　・変数名変換表_確定：手動で修正し，確定する
# 　・変数名変換表シート： Excelの数式により，自動で vars_origとvars_consの対応表が作成される
# =========================================================
# field = '刑事裁判' # 府県別ではなく裁判所別なので後回し
# field = '学齢児童' # key_col が 府県＋男女と2列になっている年があるので，後回し
# field = '郵便貯金'
# year = 1912 でエラーが出る．
# 1912_t298_02.xlsx に key_col がないのが問題．
# 原本をみると，注の特殊な表なので，連結対象から外すべき．
# これは手動で，ファイル名を _1912_t298_02.xlsx などとする？

# OK
field = 'test'  # 国費救助
# field = '盗難'
# field = '棄児'
# field = '行旅死亡人'
# field = '罹災救助'


# %% 0. 初期化
# ---------------------------------------------------------------
# panel_dir = f'{root_dir}/data/22_系列化'
# out_dir = f'{panel_dir}/{field}'
files_dir = f'{root_dir}/data/21_公開用'
in_dir = f'{files_dir}/{field}'
file_regex = '19*.xlsx'
xlsx_files = gen_file_list(in_dir, file_regex, show=True)
out_fl = f'{in_dir}/{field}_変数接続情報.xlsx'
key_col_fl = f'{in_dir}/{field}_key_col.xlsx'
varchange_fl = f'{in_dir}/{field}_変数名変遷表.xlsx'


# %% 1. long形式の全年変数一覧を作成し key_col ファイルに書き出し
# ---------------------------------------------------------------
df_varlist = gen_df_varlist(xlsx_files, in_dir)
if os.path.isfile(key_col_fl):
    print(f'{key_col_fl} は既に作成されています．')
else:
    with pd.ExcelWriter(key_col_fl, engine='openpyxl', mode='w') as writer:
        df_varlist.to_excel(writer, sheet_name="key_col", index=False)


# %% 2. key_col ファイルを作成：
# ---------------------------------------------------------------
# 手動で key_col_fl の key_colにフラグを立てる
# 系列化しないファイルは drop列にフラグを立てる
# keycol_dict: key_colの辞書

# データファイルの確認
# show_data_file(in_dir, xlsx_files)
df_key_col = pd.read_excel(key_col_fl)

df_key_col_select = df_key_col.query('key_col == 1')
print(df_key_col)

# 使わないファイルを落とす
drop_fl = list(df_key_col_select.query('drop == 1')['file'])
df_key_col_select = df_key_col_select.query('file not in @drop_fl')
key_col_dict = dict(zip(df_key_col_select['file'], df_key_col_select['col']))
xlsx_files = [i for i in xlsx_files if not i in drop_fl]

df_var_l = df_key_col.query('file not in @drop_fl')
df_var_l = df_var_l.drop('drop', axis=1)
df_var_l = df_var_l.reset_index(drop=True)


# %% 3. 変数接続情報ファイルの作成
# ---------------------------------------------------------------
# df_out = gen_table_sheet1(xlsx_files, key_col_dict, regex, tol)
df_out = gen_table_sheet1(in_dir, xlsx_files, key_col_dict, regex, tol)


# %% 4. 変数名変遷表の作成
# ---------------------------------------------------------------
df_l = gen_consvar_df_l(df_out)
df_out4 = gen_consvar_table(df_l, df_varlist, value='varname')

# %% 5. Excelファイル（変数接続情報.xlsx）に書き出し
# ---------------------------------------------------------------
# with pd.ExcelWriter(out_fl, engine='openpyxl', mode='w') as writer:
#     # df_varlist.to_excel(writer, sheet_name='全年変数一覧l', index=False)
#     df_var_l.to_excel(writer, sheet_name='全年変数一覧l', index=False)
#     df_out.to_excel(writer, sheet_name="経年接続対応表")
#     df_out4.to_excel(writer, sheet_name="変数名変遷表_提案")

# %% 6. 変数名変遷表ファイルの作成
# ---------------------------------------------------------------
gen_varchange_fl(df_var_l, df_out4, varchange_fl)


# ========================================================================
# %% 7. パネルデータ作成
# ========================================================================
# field = 'test'
# field = '棄児'
# field = '行旅死亡人'
# field = '罹災救助'
# field = '犯罪'
# field = '地価'


# 0. 初期化
# in_dir = f'{files_dir}/{field}'
# file_regex = '19*.xlsx'
# xlsx_files = gen_file_list(in_dir, file_regex, show=True)
# key_col_fl = f'{in_dir}/{field}_key_col.xlsx'
# varchange_fl = f'{in_dir}/{field}_変数名変遷表.xlsx'
vartab_sh = '変数名変換表'  # 変数名変換表のシート名
panel_fl = f'{in_dir}/{field}_panel.xlsx'

# df_key_col = pd.read_excel(key_col_fl)
# df_key_col_select = df_key_col.query('key_col == 1')
# drop_fl = list(df_key_col_select.query('drop == 1')['file'])
# xlsx_files = [i for i in xlsx_files if not i in drop_fl]

df_panel = gen_panel_data(in_dir, xlsx_files, varchange_fl, vartab_sh)
if not os.path.exists(panel_fl):
    df_panel.to_excel(panel_fl, index=False)  
else:
    print(f"File '{panel_fl}' already exists. Not overwriting.")

