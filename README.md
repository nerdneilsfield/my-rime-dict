# 自用词库

## Linux fcitx5 安装

手动安装

1. 下载 `merged_texts.dict.tar.gz` 并解压，得到词库文件 `merged_texts.dict` 。
2. 将词库文件复制到目录 `/usr/share/fcitx5/pinyin/dictionaries/` 中（如果没有这个目录，您可以自行创建）。
3. 重启 Fcitx 后即可生效。

## 安卓 fcitx5 安装

1. 下载 `merged_texts.dict.zip` 并解压，得到词库文件 `merged_texts.dict`。
2. 拼音输入模式下，在输入法键盘上选择 `输入法设置 > 管理词库` ，添加词库文件即可。

## Rime 相关输入法

1. 下载 `merged_texts.dict.zip` 并解压，得到词库文件 `merged_texts_only.txt`。
2. 移动到 `rime` 的配置文件目录。（如 Windows 的 `%APPDATA%\Rime\`，Linux/Mac 的 `~/.config/ibus/rime/` 或 `~/.local/share/fcitx5/rime/` 等）
3. 打开你所用输入方案的自定义配置文件（如 `wubi_pinyin.custom.yaml` 或 `luna_pinyin.custom.yaml`）添加 `patch` 如下。
4. 保存所有更改后，重新部署/同步 Rime（通常在输入法状态栏菜单里有“重新部署”选项）

```yaml
patch:
  engine/translators/+:
    - table_translator@merged_texts_only # 增加自定义词典翻译器
  merged_texts_only:
    dictionary: ""
    user_dict: merged_texts_only # 指向 merged_texts_only.txt
    db_class: stabledb
    enable_completion: true
    enable_sentence: true
    initial_quality: 1 # 可根据需要调整权重
```

## 手心输入法

1. 打开设置切换到词库
2. 导入用户本地词库，选择 `output/merged_texts_shouxing.txt` 导入即可

## 其它输入法

请下载 [深蓝词库转换](https://github.com/studyzy/imewlconverter)。输入格式选择无拼音纯汉字，选择文件 `output/merged_texts_only.txt` 即可，然后选择目标格式。
