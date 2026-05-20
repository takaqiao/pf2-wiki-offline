# 分类/子区数据彻底修复 — 跨会话进度账本 (LEDGER)

> 这是自我迭代任务的**唯一真相源**。每次迭代必须先读它、最后更新它。
> 状态不存在对话里,只存在这里。配套交接分析: `src-tauri/TODO_category_correctness.md`。

## 任务定义 (DoD = Definition of Done)
彻底修复离线站「分类/子区页面指向不对、和 live wiki (pf2.huijiwiki.com) 对不上」的问题,
覆盖三套机制 A(browse 关键词大桶)/ B(category 反向索引页)/ C(子区 nav stub),
**整体 + 细节**全部核对修复并验证。**期间绝不 bump 版本、绝不发版**;
**只有**所有 phase 标记 DONE 且最终验证通过后,才 bump v0.3.24 并 `release.ps1` 一次。

## 工作假设 (autonomous,无需等用户;若用户已澄清则以用户为准)
- 范围 = A + B + C 三套全包。
- 权威基准 = live `pf2.huijiwiki.com`(MediaWiki API `list=categorymembers` / `categoryinfo`)。
- "不对"同时包含【成员错(多/漏)】和【链接目标错(指向错页/死链)】。
- 修复手段优先级:能用真实 wiki 分类数据驱动的,就替换掉关键词启发式。

## 关键路径 / 基建 (P0 记录)
- **工作树**(数据 1.2GB 在此,在此 build/测试): `C:\Users\Taka\Desktop\fvtt\` —— 注意这是 git `fvttAutoTranslateTool`,**wiki 文件未被它跟踪**。
- **提交/push 仓库**: `C:\Users\Taka\pf2-wiki-offline\` (→ GitHub `takaqiao/pf2-wiki-offline`)。其 `.gitignore` 排除 `pf2wiki-scraper/out_v2/`、`_wiki_full_v2/category/`、`browse-*.html` 等 → **build 产物不入 git,只提交 build_*.py 脚本 + 文档**;产物随 release zip 发。提交时需把改动的脚本/账本从工作树同步到该仓库再 commit。
- **PARSED_DIR** = `pf2wiki-scraper/out_v2/parsed/`(256 路 hex 分片,**37071** 个 page JSON;每个含 `parse.categories=[{sortkey,category,missing?}]`)。
- **审计工具**(committable,放 `pf2wiki-scraper/cat_audit/`):
  - `build_offline_cat_index.py` —— 反转 parse.categories 成离线真值索引(同 build_v2 L867-896 口径)。
  - `dump_live_catmembers.py <targets.txt> [--limit N] [--refresh]` —— 经 pfwiki.browser() 过 CF 拉 live `categoryinfo`+全量 `categorymembers`(带 continue),按 sha1(name) 缓存。**P2 主力工具**。
  - `list_b_targets.py` —— 导出 354 个 ns=14 category 的 bare 名(B 的 diff 目标)。
- **数据缓存**(gitignored,放 `pf2wiki-scraper/out_v2/_cat_audit/`):
  - `_offline_cat_index.json` {cat: [[ns,title]...]} 全量离线真值;`_offline_cat_summary.json` 统计。
  - `_b_category_targets.txt` 354 个 B 目标名。
  - `_live/<sha1>.json` 每分类 live 成员;`_live/_index.json` 汇总。
  - `_probe_targets.txt` P0 探针 3 项。
- **离线产物清单**: 358 `category/*.html`(B) | 12 关键词桶 `browse-{feats,spells,items,creatures,ancestries,backgrounds,archetypes,classes,deities,locations,other,categories}.html`(A)+`browse-all.html` | 17 子区 stub(A/C:6 items+6 spells+5 creature-level) | 26 字母桶 browse-{A..Z,CJK,_,all}(字母导航,非分类,**范围外**) | `classes/index.html`(25 职业 hub)+`source/index.html`(14 出版物)(旁,低优先)。
- ns 直方图(离线): ns0=24649 主条目, ns4=13, ns14=354 分类页, ns102=194, ns3500=11860 数据页。

## PHASES (状态机:TODO / DOING / DONE)
- [x] **P0 准备**: DONE(2026-05-21)。读全 3 文件;scraper 过 CF 实测通过(headed 持久 profile 自动清 CF,无需人工);`categorymembers`+continue 全量枚举验证(member_count==categoryinfo.size)。路径/产物清单/工具已记录(见上)。
- [x] **P1 枚举宇宙**: DONE(2026-05-21)。全集已枚举入 WORKLIST。离线 B 真值索引已建(3604 distinct cat,其中 3294 被标 `missing:true`=红链分类无 Category 页;仅 354 有 ns=14 页 → 358 html 多出 4 待查)。A 的 BUCKETS 关键词字典、C 的 STUBS 映射、class hubs 已读全。
- [ ] **P2 拉基准**: TODO ← **下次从这里**。先跑 B:`dump_live_catmembers.py out_v2/_cat_audit/_b_category_targets.txt`(354 个,headed,约 5-10min)。再拉 A 的 12 个锚分类 + C 的子区/传统分类(名称需先在 live 核实存在,见 FINDINGS 的"待核实映射")。
- [ ] **P3 diff + 定位**: TODO。逐项 diff 离线 vs live → FINDINGS,标 A/B/C + 根因。
- [ ] **P4 修复**: TODO。按根因改 build_*.py / 数据,真实 wiki 分类驱动取代关键词启发式;改一类、重生成、复核 diff 归零。
- [ ] **P5 整体重建 + 验证**: TODO。全量重跑 build_*.py;抽样+全量 diff 0 残留;`diagnostics/acl_probe.mjs`;死链复查。
- [ ] **P6 发版(仅此时 bump)**: TODO。见铁律。

## WORKLIST (每项: 名称 | 机制 | 状态 | 备注)
### B — 358 category/ 页(354 ns=14 + 4 待查)
- [ ] 354 个 ns=14 分类 | B | TODO | 目标名见 `_b_category_targets.txt`;离线成员=`_offline_cat_index.json`;P2 拉 live 全量 diff。含大量维护/模板类(Infobox/Mbox/Huiji template/GM帷幕…)与内容类。
- [ ] 358-354=4 个多出的 category html | B | TODO | 来源未知(疑 build_dead_stubs / redirect)。P3 列出具体 4 个文件名定位。

### A — 12 关键词桶(browse_v2.classify 启发式)
- [ ] feats | A | TODO | 关键词 [专长,feat];拟锚定 live `Category:专长`(仅 ns0)。
- [ ] spells | A | TODO | 关键词 [法术,spell,戏法,聚能];拟锚 `Category:法术`。**已知污染**:含"法术"子串的 feat 误入。
- [ ] items | A | TODO | 关键词 [物品,装备,武器,护甲,消耗品,戴持物品,符文,法器,item];拟锚 `Category:物品`。
- [ ] creatures | A | TODO | 关键词 [怪物,creature,monster];拟锚 `Category:怪物`(**待核实该分类是否存在/名称**)。
- [ ] ancestries | A | TODO | [祖先,ancestry];拟锚 `Category:祖先`(待核实)。
- [ ] backgrounds | A | TODO | [背景,background];拟锚 `Category:背景`(待核实)。
- [ ] archetypes | A | TODO | [变体,archetype];拟锚 `Category:变体`(**名称很可能不对**,待核实)。
- [ ] classes | A | TODO | [职业,class];可改用 25 职业 allowlist 或 `Category:职业`。
- [ ] deities | A | TODO | [神祇,deity];拟锚 `Category:神祇`(待核实)。
- [ ] locations | A | TODO | [地点,location,城市,国家,区域];拟锚 `Category:地理`(离线 1145)或 地点(待核实)。
- [ ] other | A | TODO | [状态,特征,trait,condition];**最脏**:吞掉所有 (特征) 分类几千页。拟拆分/重定义或废弃。
- [ ] categories | A | TODO | ns=14 全量桶;基本对应 B 全集,核实是否冗余。
- [ ] browse-all | A | TODO | 全条目字母表;核实计数。

### C — 17 子区 nav stub(全部 meta-refresh 跳到**未过滤**父页)
- [ ] items: weapons/armor/consumables/worn/runes/implements(6) | C | TODO | 标签 武器/护甲/消耗品/佩戴物品/符文/法器;**当前 url=browse-items.html 无过滤**。
- [ ] spells: arcane/divine/occult/primal/cantrips/focus(6) | C | TODO | 标签 奥术/神圣/神秘/原初/戏法/专注;传统分类 live 名待核实(可能 秘法/玄秘 等)。
- [ ] creatures: level 0-3/4-7/8-12/13-17/18-25(5) | C | TODO | 按等级分段;wiki 可能无等级分类→需从 creature level 数据字段驱动,非分类。

### 旁(低优先)
- [ ] classes/index.html | hub | TODO | 25 职业 allowlist(KNOWN_CLASSES),链 `../pages/<职业>.html`;核实链接有效。
- [ ] source/index.html | hub | TODO | 14 出版物,链 `browse-all.html?q=…`;**?q= 无 JS 读取→筛选失效**(次要)。

## FINDINGS (P3 填充;每条: 项 | 机制 | 离线 vs live 差异 | 根因 | 修复状态)
### 预备发现(P0/P1 已观察,P3 量化确认)
- **A 本质缺陷**(高):browse 桶 = 关键词子串 any-match,非 wiki 分类。`特征` 命中所有 trait 页(罕见/魔法/变体/常见…(特征)共数千)灌进 `other`;`法术` 子串把 feat 拉进 spells;title 也进 blob;一页多桶。→ 必须改为真实分类驱动。
- **C 功能性失效**(高):17 个子区 stub 全是 `<meta refresh url=browse-{items,spells,creatures}.html>`,**不带任何过滤**,标签仅出现在"正在跳转"文字里 → 6 个法术子区/6 个物品子区/5 个怪物等级**全落到同一张未过滤父表**。子区区分纯装饰。→ 需真实子分类/传统/等级驱动的过滤内容。
- **B 构造上忠实 live**:成员=反转 parse.categories,理论=live 每页分类盒。P0 探针实测小差(离线略少于 live):法术 1761 vs live 1765(+4)、专长 4872 vs 4875(+3)、魔法(特征) 2405 vs 2423(+18)。疑 scrape 略陈旧/个别页未抓全。P3 比对成员名单定位是 staleness 还是漏抓。
- **3294/3604 分类被标 missing:true**:红链分类(被引用但无 Category 页),build_v2 不为其生成页(只为 354 ns=14 生成)→ 与 358 数差 4 待查。
- **待核实映射**(P2 必做):A/C 拟锚定的 live 分类名(怪物/祖先/背景/变体/神祇/地理 + 法术传统 奥术/神圣/神秘/原初)是否存在、确切中文名 → 用 `dump_live_catmembers.py` 探测确认后再定 P4 映射表。

## 迭代日志 (每次运行追加一行: 日期 | 本次干了什么 | 下次从哪继续)
- 2026-05-21 | 建账本骨架 + 自迭代 prompt(本次未动逻辑) | 下次从 P0 开始
- 2026-05-21(iter2) | P0 DONE(读全状态+CF 探针实测过+路径/产物/工具记录)+ P1 DONE(全集枚举入 WORKLIST,建离线真值索引 3604cat,读全 A/B/C 脚本,导出 354 B 目标)+ 建 3 个 cat_audit 工具+预备发现(A 关键词脏/C 子区装饰/B 小 staleness)| 下次从 **P2**:跑 `dump_live_catmembers.py _b_category_targets.txt` 拉 354 B 分类 live 成员(headed ~5-10min),再拉 A 锚分类+C 传统分类(先核实名称),然后 P3 diff B。
