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
- [~] **P2 拉基准**: **B-part DONE**(354 全拉,0 失败,缓存 `out_v2/_cat_audit/_live/`,info_size 全对齐)。**A/C-part TODO**: A 的锚分类**多数已在 B 缓存里**(专长/法术/物品/生物/背景/变体/职业/地理/特征/戏法/聚能/武器/护甲/符文 共 14 个都是 ns=14,已拉)→ **无需再拉**;仅需补:缺失锚的真名(祖先?族裔? 神祇?信仰? — live 探测确认)+ C 的法术传统(奥术/神圣/神秘/原初,疑「(特征)」后缀)+ 物品子类(消耗品/佩戴物品/法器,疑「(特征)」后缀)。
- [~] **P3 diff + 定位**: **B DONE**(正确/staleness)。**A 已量化**(`diff_a.py`:每桶大错配,真锚名已 probe 确认;creatures/archetypes 锚非单一分类,待 investigate)。**C 子类锚名已 probe**(见 FINDINGS);法术传统/怪物等级需数据驱动。剩:creatures/archetypes 锚 investigate + C 数据驱动方案。
- [ ] **P4 修复**: TODO。B 无需改码(staleness 由 P6 重抓解决)。**重点 = A+C**:按根因改 build_browse_v2.py(关键词→真实分类驱动)+ build_nav_stubs.py(装饰 stub→真实子类过滤内容);改一类、重生成、复核 diff 归零。
- [ ] **P5 整体重建 + 验证**: TODO。全量重跑 build_*.py;抽样+全量 diff 0 残留;`diagnostics/acl_probe.mjs`;死链复查。
- [ ] **P6 发版(仅此时 bump)**: TODO。见铁律。

## WORKLIST (每项: 名称 | 机制 | 状态 | 备注)
### B — 358 category/ 页(354 ns=14 + 4 待查)
- [x] 354 个 ns=14 分类 | B | **DONE/已验证正确** | 全量 diff(hosted-ns {0,4,14,102,3500}):**317/354 完全一致**;37 个有差(97 漏+22 多)**全部=staleness**(94 漏=2026-05-19 后新增页:健康腰带/冒烟之剑/冰川巨锤/风暴战锤/《地狱破灭》/《幽暗地脉》等约 13 物品+8 出版物;22 多+3 漏=remaster 重分类,如 命匣 同时出现在 missing[2r 标签] 与 extra[2e 标签])。**build_v2.py 反转 parse.categories 逻辑正确,无需改码**。报告:`_b_diff_report.json`/`_b_findings_analysis.json`。
- [ ] 358-354=4 个多出的 category html | B | TODO(低优) | 来源未知(疑 build_dead_stubs/redirect)。次要;B 已在 354 真分类上验证正确。

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
- **A 已量化(确认极脏,`diff_a.py` ns=0 vs 真分类)**:每桶都大幅错配。
  桶 | 当前 | 真分类 | 误含(多) | 漏(少) | 真锚:
  feats 6625/专长4874(+1753) | spells 2442/法术1761(+681) | items 9469/物品3399(**+6080**) | creatures 1466/生物**2**(几乎全错) | ancestries **1**/族裔245(**漏245**) | backgrounds 474/背景462(+12,最准) | archetypes 2375/变体**0** | classes 4941/职业419(**+4522**,职业专长污染) | deities 96/信仰476(**漏406**) | locations 124/地理1145(**漏1061**) | other **15949**/无锚。
  根因 = 关键词子串(物品/职业/特征 命中海量导航/专长/trait 页)+ title 进 blob + 一页多桶。
  **真锚名(probe 确认,`_ac_probe_results.json`)**:creatures=生物、ancestries=**族裔**(非祖先)、deities=**信仰**(非神祇)、locations=**地理**(非地点)、archetypes=变体。
  **⚠️ 两个锚本身不是单一 ns0 分类**:生物(仅 2 ns0)、变体(0 ns0)→ creatures/archetypes 不在单一分类,散在来源/类型分类(top50 无怪物类)→ 需数据驱动或分类并集(待 investigate)。
- **C 功能性失效**(高):17 个子区 stub 全是 `<meta refresh url=browse-{items,spells,creatures}.html>`,**不带任何过滤**,标签仅出现在"正在跳转"文字里 → 6 个法术子区/6 个物品子区/5 个怪物等级**全落到同一张未过滤父表**。子区区分纯装饰。→ 需真实子分类/传统/等级驱动的过滤内容。
- **C 子类锚名(probe 确认)**:物品子类 weapons=武器、armor=护甲、runes=符文(均存在/已在 B 缓存);worn=**穿戴物品**(407,非「佩戴物品」);consumables=**消耗品（特征）**(1111);**implements=法器 不存在**(0/missing,可能是数据属性);装备(equipment)=408(红链有员)。**⚠️ 法术传统无可用分类**:奥术/神圣/神秘/原初 bare 全 missing;仅 奥术（特征）=110 有员,神圣/神秘/原初（特征）全空 → **传统不是分类驱动,得读每法术的 tradition 数据字段**(ns=3500 data 或 infobox)。creatures 等级分段同理:wiki 无等级分类 → 读 creature level 数据。
- **B 已验证正确(已结案)**:354 ns=14 分类全量 diff,317 完全一致,37 个差异(97 漏+22 多)经 `analyze_b_findings.py` 逐条根因 = **100% staleness**(94 漏=新增页不在离线语料;22 多+3 漏=remaster 重分类,命匣同时在 missing[2r] 和 extra[2e] 是铁证)。**build_v2.py 无 bug**。修复=P6 release 重抓(注意需跑 title harvest 以发现新增页,否则只重抓旧清单漏掉新页)。
- **3294/3604 分类被标 missing:true**:红链分类(被引用但无 Category 页),build_v2 不为其生成页(只为 354 ns=14 生成)→ 与 358 数差 4 待查(低优)。
- **A/C 锚分类真名核实(已部分确认,见 `_anchor_coverage.json`)**:有 ns=14 页且已拉 live 的 14 个=专长/法术/物品/**生物**/背景/变体/职业/**地理**/特征/戏法/聚能/武器/护甲/符文。**关键纠错**:creatures 真分类=**生物**(A 的 keyword 用「怪物」是错的);locations 真分类=**地理**(非「地点」);archetypes=**变体**(非「原型」)。**仍缺 ns=14 页(需 live 探测真名)**:祖先(?族裔)、神祇(?信仰)、消耗品/佩戴物品/法器(疑「(特征)」后缀)、法术传统 奥术/神圣/神秘/原初(疑「(特征)」后缀)。

## 迭代日志 (每次运行追加一行: 日期 | 本次干了什么 | 下次从哪继续)
- 2026-05-21 | 建账本骨架 + 自迭代 prompt(本次未动逻辑) | 下次从 P0 开始
- 2026-05-21(iter2) | P0 DONE(读全状态+CF 探针实测过+路径/产物/工具记录)+ P1 DONE(全集枚举入 WORKLIST,建离线真值索引 3604cat,读全 A/B/C 脚本,导出 354 B 目标)+ 建 3 个 cat_audit 工具+预备发现(A 关键词脏/C 子区装饰/B 小 staleness)| 下次从 **P2**:跑 `dump_live_catmembers.py _b_category_targets.txt` 拉 354 B 分类 live 成员(headed ~5-10min),再拉 A 锚分类+C 传统分类(先核实名称),然后 P3 diff B。
- 2026-05-21(iter2 续) | **P2-B + P3-B DONE**:拉全 354 B 分类 live(0 失败)→ `diff_b.py` → `analyze_b_findings.py`。**B 结案=正确,119 差异全 staleness,build_v2 无 bug**(命匣 2e→2r remaster 为铁证)。建 diff_b.py/analyze_b_findings.py 工具。锚覆盖核实:creatures 真名=**生物**(非怪物)、locations=**地理**、archetypes=**变体**。| 下次从 **P3-A**。
- 2026-05-21(iter3) | **P3-A 量化 + A/C 锚名 probe**:补拉 28 候选锚(`_ac_probe_targets.txt`)→ 确认 ancestries=**族裔**(非祖先)、deities=**信仰**(非神祇);法术传统无分类(仅奥术(特征)110,余空)→ 须数据驱动。`diff_a.py`:每桶大错配(items+6080、classes+4522、archetypes+2375 误含;locations 漏1061、deities 漏406、ancestries 漏245)。建 diff_a.py。**A 是用户「对不上」主因,实锤**。| 下次:investigate creatures/archetypes 真锚(生物=2/变体=0 ns0,需查这些页实际分类)→ 定 A 的 P4 映射 → 改 build_browse_v2.py(分类驱动)→ 重建复核;再处理 C(物品子类用分类、传统/等级用数据字段)。
