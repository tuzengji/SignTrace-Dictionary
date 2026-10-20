# SignTrace Dictionary · 手语词典原始数据

SignTrace 当前使用词典的原始图文数据快照，包含 **6,707 个手语词条、8,704 个义项、6,707 张词典原图**。快照日期为 **2026-10-20**，对应已完成词名校正和漏项恢复的 `dictionary-enrichment-20261017` 版本。

保留词典原始动作说明、词名、打法编号、首字母、分册信息及图片。**不包含增强视觉描述、模型生成的动作结构或分步特征**。其中 `description` 是原书动作说明，属于本次公开的原始内容。

## 下载与文件

```sh
git clone https://github.com/tuzengji/SignTrace-Dictionary.git
cd SignTrace-Dictionary
python3 scripts/verify.py
```

也可以使用 GitHub 的 **Code → Download ZIP** 下载完整快照。图片总计约 354 MB，数据库和 JSONL 均可独立读取；图片文件直接保存在仓库中。

| 路径 | 内容 |
| --- | --- |
| `data/signs.db` | 新建的 SQLite 数据库，仅有 `signs`、`meanings` 两张原始数据表 |
| `data/signs.jsonl` | 每行一个词条，包含完整原始字段及该词条的全部义项 |
| `data/images/` | 6,707 张 JPEG 词典线描图，保留原文件名和字节内容 |
| `data/manifest.json` | 数量、字段清单、原始数据行摘要及每个数据文件的 SHA-256 |
| `scripts/verify.py` | 无外部依赖的完整性检查 |
| `scripts/export_original.py` | 按字段白名单从本地数据库重新导出的脚本 |

图片路径相对于 `data/`，例如 `images/v1_txt005_2.jpg` 对应 `data/images/v1_txt005_2.jpg`。

## 数据结构

```text
signs:
  id              原词条 ID，保持现有编号
  image_path      相对于 data/ 的原图路径
  description     原书动作说明
  source_entry    原词条标题，保留同义词和打法标记
  letter          首字母分区
  volume          原书分册编号

meanings:
  id              原义项 ID
  sign_id         对应 signs.id
  text            词名或同义词
  variant_index   打法编号；没有编号时为 null
  order_in_entry  义项在原词条内的顺序
```

同一词条可以有多个义项，同一词语也可能对应不同打法和图片。6,707 是动作词条数，8,704 是义项记录数；义项 ID 保留原值，不重新连续编号。

查询示例：

```sh
sqlite3 data/signs.db "
SELECT s.id, m.text, m.variant_index, s.description, s.image_path
FROM signs s JOIN meanings m ON m.sign_id = s.id
WHERE m.text = '生日'
ORDER BY s.id, m.order_in_entry;
"
```

Python 示例：

```python
import json
from pathlib import Path

data_dir = Path("data")
with (data_dir / "signs.jsonl").open(encoding="utf-8") as stream:
    entry = json.loads(next(stream))
print(entry["description"])
print(entry["meanings"])
print(data_dir / entry["image_path"])
```

## 来源与版本

图文来自《国家通用手语词典（全四册）》的 EPUB 提取结果。早期公开数据见 [chinese-sign-language-dictionary](https://github.com/tuzengji/chinese-sign-language-dictionary)，其 6,699 条版本是本项目的原始数据基础。

当前快照保留 2026-10-17 根据原书完成的词名、排版空格、同义词与打法标记修复，以及恢复的 8 个漏抽取词条：航标、魔术②、疏导、英国、账户、昼夜、主角（主演）、壮丽。原有词条 ID 保持不变，恢复词条使用 6700–6707。

这里的“原始”指当前词典中来自原书的字段，已经包含人工核对后的提取修复；不代表未经整理的 EPUB，也不包含完整原书、研究材料或用户查询记录。

导出时新建 SQLite 文件，并且只读取两张原始数据表的指定字段；没有复制增强库后再删除表。`llm_description`、`llm_struct`、所有 `visual_*` 表以及模型响应均不进入数据文件。

## 重新导出

需要自行提供本地源数据库和原图目录，脚本不包含私有资产路径或认证配置：

```sh
python3 scripts/export_original.py \
  --source-db /path/to/signs_codex_v3.db \
  --images-dir /path/to/images \
  --output /path/to/new-export/data \
  --snapshot-date 2026-10-20 \
  --source-version dictionary-enrichment-20261017
python3 scripts/verify.py /path/to/new-export/data
```

目标目录必须不存在。导出以只读事务读取源数据库，原始词条与义项逐行核对，图片按引用复制；完成后校验表结构、外键、JSONL 对应关系和全部文件摘要。

## 使用范围

沿用[早期数据仓库](https://github.com/tuzengji/chinese-sign-language-dictionary)的使用约定：仅供学习、研究和无障碍技术开发等非商业用途。原书文字与图片版权归原出版方、编制单位及相关权利人所有；本仓库不另行授予这些图文的商业使用许可。权利人可通过仓库 Issues 联系维护者。
