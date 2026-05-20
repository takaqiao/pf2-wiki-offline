# TODO（下个会话）：分类 / 子区正确性核对

> 用户观察（2026-05-21）：「各分类/子区里很多页面指向的都不太对，和 wiki（pf2.huijiwiki.com）对不上。」
> 本会话只**写交接文档**，不处理。下个会话据此核对 + 修。

## 关键背景：离线站有 **3 套不同的"分类"机制**，性质完全不同

| 机制 | 文件 | 生成方式 | 是否对应真实 wiki 结构 |
|---|---|---|---|
| **A. browse 大桶** `browse-{feats,spells,items,creatures,...}.html` | `_wiki_full_v2/build_browse_v2.py` | **关键词子串匹配** `classify()`（`BUCKETS` 字典 L31-44），把每页的「分类名+标题」拼成字符串，含任一关键词就归入该桶 | ❌ **自创启发式，本来就不是 wiki 的分类**。最可疑的「对不上」来源 |
| **B. category/ 反向索引页**（358 个）`_wiki_full_v2/category/*.html` | `build_v2.py` L868-896（`category_members`） | 反转每页的 `parse.categories`（MediaWiki 真实分类）填充 | ✅ 理论上忠实 wiki（取决于 scrape 的 parse.categories 准不准） |
| **C. 子区 nav stub** `browse-items-weapons.html` / `browse-spells-arcane.html` / `browse-creatures-level-0-3.html` 等 | `build_nav_stubs.py`（`STUBS` 字典 L13+） | **跳转 stub** → 指向父 browse 页 + 一个筛选标签（如 武器→`browse-items.html` 筛"武器"、奥术→`browse-spells.html` 筛"奥术"） | ⚠️ 取决于父页内容 + 筛选标签是否对得上 |
| （旁）class hubs | `build_class_hubs_v2.py` | 25 个职业 hub | 待查 |

## `classify()` 为什么会"指向不对"（A 的核心缺陷）

`build_browse_v2.py:103-112`：
```python
cat_blob = (" ".join(cats) + " " + title).lower()
for bucket, keys in BUCKETS.items():
    for k in keys:
        if k.lower() in cat_blob:   # 子串匹配，any-match
            out.add(bucket); break
```
- **子串过宽**：含"法术"关键词 → spells 桶。一个「法术专长」类 feat 的分类里有"法术" → 同时进 feats **和** spells。
- **关键词撞车**：`items` 含"法器"、`other` 含"trait/特征"——`特征` 命中面极大；`物品/装备/武器/护甲/...` 任一子串都进 items。
- **一页多桶**：`classify` 返回 set，一页可落入多个桶（设计如此，但放大了误分类）。
- 结论：browse 大桶 ≈ 关键词近似，**不等于** wiki 的真实分类树。"和 wiki 对不上"大概率主要指这里。

## 权威对照源

- **live wiki**：`https://pf2.huijiwiki.com`（HuijiWiki = MediaWiki）。真实分类可用 MediaWiki API 查：
  `api.php?action=query&list=categorymembers&cmtitle=Category:<名>&cmlimit=max`
- **scraper 基建已就绪**：`C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\`（CF cookie warmup + curl_cffi + Chrome TLS 模拟，能过墙过 CF）。可批量拉真实分类成员做 diff。
- **离线侧真值**：每页 JSON 的 `parse.categories`（在 `PARSED_DIR`，scraper 输出）。category/ 页就是它反转来的。

## 下个会话的核对计划（建议顺序）

1. **先定位"错"在哪一套**（A/B/C）——让用户指 1-2 个具体"指向不对"的页面，或自己抽样：
   - 打开 v0.3.23 app（已修复，外链/导航可用），点几个分类/子区，记下「页面 → 看到的成员/跳转 → 期望(wiki)」。
2. **B（category/ 反向索引）核对**（若怀疑这里）：
   - 抽 N 个分类，用 MediaWiki API 拉 live `categorymembers`，与 `category/<名>.html` 的成员列表 diff。
   - 若 diff 大 → 可能 scrape 的 `parse.categories` 不全（action=parse 对 ns=14 不返 categorymembers，见 build_v2.py L868 注释）→ 需改用 API `list=categorymembers` 重抓分类成员，而非反向索引。
3. **A（browse 大桶）核对**：
   - 评估 `classify()` 误分类率（抽样看 browse-spells 里有多少其实是 feat 等）。
   - 决策：要么收紧关键词/改成基于真实分类映射，要么明确 browse 桶只是"近似导航"并接受。
4. **C（子区 nav stub）核对**：
   - 检查 `build_nav_stubs.py` 的 `STUBS` 映射每个子区 → 父页 + 筛选标签是否正确（如 spells-arcane 的"奥术"筛选在父页能否筛出正确法术；creatures-level 段位划分对不对）。
   - 注意父 browse 页要真的支持该筛选标签（filter.js / data 属性）。
5. **修复后重建 + 发版**：改的是 `_wiki_full_v2/` 内容/构建脚本 → 需重跑相应 build_*.py 重生成受影响页 → 走 `release.ps1`（**纯内容改动用 `update_content.ps1`，不重编 exe**；基准用干净的 `pf2-wiki-offline_0.3.23_x64-portable` 文件夹）。

## 待用户澄清（下个会话先问）

- 「子区」具体指哪类页？browse 子桶（weapons/arcane/level 段）还是 category 页里的子分类？
- 看到的"不对"是 **成员错**（页面列了不该有的/漏了该有的）还是 **链接目标错**（点进去到错误页/死链）？
- 对照基准就是 live `pf2.huijiwiki.com` 的分类吧？（确认后好批量 API diff）

## 相关文件速查
- `_wiki_full_v2/build_browse_v2.py`（BUCKETS L31, classify L103, render L115）
- `_wiki_full_v2/build_v2.py`（category 反向索引 L868-896）
- `_wiki_full_v2/build_nav_stubs.py`（子区 stub STUBS L13+）
- `_wiki_full_v2/build_class_hubs_v2.py`
- `_wiki_full_v2/build_dead_stubs.py`、`build_browse_letters_v2.py`
- 产物：`_wiki_full_v2/browse-*.html`、`category/*.html`
- scraper：`pf2wiki-scraper/`（含 cookie warmup、dump 脚本）
