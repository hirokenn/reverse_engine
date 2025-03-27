from fns_general import _get_tab_info_from_name, _get_machineready_data
import pandas as pd
import re
import math

# =============================================================================
# =============================================================================
# 完成済み関数
# =============================================================================
# =============================================================================


# %% ファイル名のリストの中で，指定年のファイルを横に外部結合する関数
# =============================================================================
def _merge_files_of_same_year(in_dir, xlsx_files, year, key_col_dict=None):
    # year = 1905
    # 該当年のファイルだけリストに残す
    file_list = [file for file in xlsx_files
                 if _get_tab_info_from_name(file)[0] == year]
    # 初期化
    df_out = None
    lst = []  # 各ファイルの列数
    ncol_lst = []  # 各ファイルが何列目に入るか

    for fl_name in file_list:
        # fl_name = '1905_t122_01.xlsx'
        # fl_name = '1905_t122_02.xlsx'
        # fl_name = '1905_t122_03.xlsx'

        df = _get_machineready_data(f'{in_dir}/{fl_name}')

        # 列名を{tab_no}_{tab_subno}_c{列名}に変更
        colnames = ['t'+'_'.join(str(n) for n in _get_tab_info_from_name(fl_name)[1:])
                    + '_c' + str(col) for col in df.columns]

        # key列の列名を key1, key2... に上書きする
        if fl_name in key_col_dict.keys():
            key = key_col_dict[fl_name]
        else:
            key = 0
        colnames[:key+1] = [f'key{i}' for i in list(range(key+1))]
        df.columns = colnames

        # key内に重複がある場合は，その左の列と結合した文字列で置き換える →これでユニークにする
        key_cols = df.iloc[:, :key+1]
        key_cols = key_cols.fillna('')
        new_key = key_cols.apply(lambda row:
                                 ''.join(row.values.astype(str)), axis=1)
        # key列がユニークでない（重複がある）場合，横連結した new_key で置換する
        df.iloc[:, key] = df.iloc[:, key].mask(
            df.iloc[:, key].duplicated(keep=False), new_key)
        # df
        # !!TODO: 本当は重複チェックをした方がよい: df.iloc[:, key].duplicated()

        # key_col +データ列のみ残す
        df = df.iloc[:, key:]
        df = df.rename(columns={df.columns[0]: 'key_col'})

        if df_out is None:
            df_out = df.copy()
        else:
            # データフレームを横結合
            df_out = pd.merge(df_out, df, how='outer').reset_index(drop=True)

            lst.append(len(df.columns))  # 列数カウント
            sums = 0
            for i, l in enumerate(lst):
                if i == 0:
                    sums = sums + l
                else:
                    sums = sums + l - len(range(key+1))
                ncol_lst.append(sums)
            ncol_lst = [int(ncol-1) for ncol in ncol_lst]

        # # !!TODO: データが重複している列は基本ないと思われるので，以下は今後の課題
        # # データが重複している列を削除
        # # https://stackoverflow.com/questions/43347939/all-possible-combinations-of-columns-in-dataframe-pandas-python
        # cc = list(combinations(df_out.columns[key+1:, ], 2))
        # # c = ('t241_0_c2', 't241_0_c3')
        # # test: 本番は if not の 'not' を外す
        # duplicated_cols = [c[0]
        #                    for c in cc if not df_out[c[0]].equals(df_out[c[1]])]
        # # duplicated_cols = [c[0] for c in cc if df_out[c[0]].equals(df_out[c[1]])]
        # duplicated_cols = pd.Series(duplicated_cols).drop_duplicates()
        # df_out = df_out.drop(columns=duplicated_cols)

    # 結合後のデータフレームを返す
    return df_out, ncol_lst


# %% 2つの統計表を渡し，経年接続できる変数の辞書を返す関数
# =============================================================================
def _gen_linked_var_dict(df1, df2, key_cols, tol=1, debug=False):
    '''
    2つの変数列を比較し，一定数以上一致するならば，経年接続できると判断する

    key_cols: 各年統計表の共通列（na_colsとkey_colsの合併：府県列とデータに年号を含む列のindex）
    tol: 不一致行数の許容度

    Return 経年接続できる変数の辞書
    '''
    # 出力する辞書の初期化
    dics = {}

    # key_col以外の列indexのベクトル
    # key_col は 0 に決め打ちなので，1以上
    # df1_colname = [col for col in list(df1.columns) if col not in key_cols]
    # df2_colname = [col for col in list(df2.columns) if col not in key_cols]
    df1_colname = list(df1.columns)[1:]
    df2_colname = list(df2.columns)[1:]

    for col1 in df1_colname:
        for col2 in df2_colname:
            # col1 = df1_colname[0]
            # col2 = df2_colname[0]
            # print(col1)
            # print(col2)

            # df1とdf2の指定列を抽出
            df1_copy = df1.copy()
            df2_copy = df2.copy()
            val1_lst = df1_copy.iloc[:, key_cols].values.tolist()
            val2_lst = df2_copy.iloc[:, key_cols].values.tolist()
            df1_copy['keys'] = [tuple(val) for val in val1_lst]
            df2_copy['keys'] = [tuple(val) for val in val2_lst]
            dat1 = df1_copy[['keys', col1]]
            dat2 = df2_copy[['keys', col2]]
            # print(dat1)
            # print(dat2)

            # 突合する (key列をキーに突合)
            df_merge = dat1.merge(dat2, left_on='keys',
                                  right_on='keys', how='outer')
            df_merge.columns = ['keys', 'df1', 'df2']
            # print(df_merge)

            # If both key columns contain rows where the key is a null value, those rows will be matched against each other. This is different from usual SQL join behaviour and can lead to unexpected results.
            # dat1 か dat2 が空のときおかしくなる
            # df_merge.dtypes
            if (df_merge['df1'].dtype == object) | (df_merge['df2'].dtype == object):
                df_merge['union'] = 9999
            else:
                df_merge['union'] = df_merge['df1'] - df_merge['df2']

            # 相互参照できる行数
            nrow = df_merge['union'].count()
            # 重複行数　＝　数値が相違ない行数
            nequal = (df_merge['union'] == 0).sum()

            # 検証用のprint
            if debug:
                print(f'\n !!! Checking col1={col1} col2={col2}')
                print(df_merge)
                print(f'nrow = {nrow}, nequal = {nequal}')

            # 重複行の数が一定以上なら経年接続できると判定する
            # (nrow - tol >= 2) & (nequal >= nrow - tol)
            if (nrow - tol >= 2) & (nequal >= nrow - tol):
                dic_out = {col1: col2}
                dics.update(dic_out)
                break
            else:
                # print(f'\n Not match!! col1={col1} col2={col2}')
                # dic_out = {col1: 'NaN'}
                dic_out = {col1: float('nan')}
                dics.update(dic_out)

            # print(dics)

    return dics


# %% 各成分が't{tab_no}_{tab_subno}_c{列index名}'のリストを与えたとき，各成分が(tab_no, tab_subno, 列index名)のリストを返す
# =============================================================================
def _get_tabcol_info_from_textlst(col_lst):
    regex = r'(t)?([0-9]+)?(_)?([0-9]+)?(_c)?([0-9]+)'
    col_tpls_lst = []
    for val in col_lst:
        if val is None or type(val) is int:
            col_tpls_lst.append(val)
        elif str(val) == 'nan':
            col_tpls_lst.append((math.nan, math.nan, math.nan))
        else:
            # 与えたリストの各要素からタブの情報を取り出す
            tab_no = int(re.search(regex, val).group(2))
            tab_subno = int(re.search(regex, val).group(4))
            col_num = int(re.search(regex, val).group(6))
            col_tpls_lst.append((tab_no, tab_subno, col_num))
    return col_tpls_lst


# # test
# col_lst = ['t216_0_c1', 't216_0_c2', 't216_0_c3', None, 0, math.nan]
# _get_tabcol_info_from_textlst(col_lst)


# %% 辞書のkeyからリストを作成
# =============================================================================
def _dic2list_onkey(dic, key):
    '''
    dic:与えた辞書（valueとkeyに対応関係がある）
    key:辞書のkey

    Return: 辞書のkeyとvalueをつなげたものをリストとして返す（リストの最後は辞書）
    '''
    if dic is None or key is None:
        return []
    lst = []
    # 辞書を複製
    dic_copy = dic.copy()
    # key, valueをつなげてリストとして返す
    if key not in dic_copy:
        return [key, dic_copy]  # 残った辞書
    else:
        # 取得したkey&valueは削除
        dic_copy.pop(key)
        return [key] + _dic2list_onkey(dic_copy, dic[key])


# # %% test
# dic = {'a': 'b',
#        'b': 'c',
#        'd': 'e'
#        }
# key = 'a'  # a -> b, b -> c なので[a,b,c]
# dic2list_onkey(dic, key)  # ['a', 'b', 'c', {'d': 'e'}]
# key = 'd'  # d -> e なので[d, e]
# dic2list_onkey(dic, key)  # ['d', 'e', {'a': 'b', 'b': 'c'}]


# %% 辞書からデータフレームを作成する再帰関数
# =============================================================================
def _dic2data(dic, df):
    '''
    dic:辞書（valueとkeyに対応関係がある）
    df_out:consvar{1}～consvar{i-1}列をもつデータフレーム
    Return: 再帰的にconsvar{i}列を割り当て，dicの成分をすべて接続しデータフレームのみを返す
    '''
    # 各keyから得られる列にconsvar{i}を割り当てる
    # 辞書の一つ目のkeyからリンクする列のリストを取得
    keys = list(dic.keys())
    lst = _dic2list_onkey(dic, keys[0])
    # リンクしなかったものの残り
    dic_copy = lst[-1].copy()

    # consvarの添え字
    if df is None:
        i = 1
    else:
        i = len(df.columns)-2

    # df_out の作成
    df_out = pd.DataFrame(lst[:-1],
                          columns=['year', 'tab_no', 'tab_subno', f'consvar{i}'])

    # df_outに接続
    if df is None:
        df_out = df_out.copy()
    else:
        df_out = pd.concat([df, df_out])

    # 古い年からのソートに
    df_out = df_out.sort_values(
        ['year', 'tab_no', 'tab_subno'], ascending=True)

    # key, valueをつなげてリストとして返す
    if not any(dic_copy):
        return df_out  # 残った辞書
    else:
        # 残った辞書の最初のkeyをもとにconsvar{i+1}列を作成しデータフレームを作成
        return _dic2data(dic_copy, df_out)
