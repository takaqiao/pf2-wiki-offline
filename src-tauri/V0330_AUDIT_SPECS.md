# v0.3.30 审计修复规格(工作流原始产出)

> 自动提取自 42-agent 审计工作流 wf_c93f942e-778 (2026-06-10)。

## 已知根因(RC)核验

### RC1 — status: present

**Evidence**

[1] 代码确认 — C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py 行866-879:NS_BARE_PRIORITY={0:0,102:1,3500:2,4:3,14:4}(行866);索引循环行869-879。行875 `if bare != t:` 使 ns0/102 无冒号标题(bare==t)永不登记 bare_owner_prio;行877-879 中后到的 ns14 "Category:武器"(bare="武器"≠t, prio=4)发现裸键无记录 → 直接覆写 title_index["武器"]=("category",…)。消费端 rewrite_links 行188 `resolved=redirect_map.get(target_title,target_title)`、行191 `title_index.get(resolved) or title_index.get(target_title)` 用该被污染裸键解析内链。
[2] metadata 碰撞枚举 — C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json:40,736 页(ns0=28,312, ns102=197, ns14=354, ns3500=11,860, ns4=13),redirect_map 5,799 条。ns0/102 且 bare==t 共 28,509;与 ns14 "Category:"+t 碰撞 = 160 个。逐条模拟原循环:160/160 全部裸键被覆写到 'category'。前30:GM帷幕/NPCC/《NPC核心》/《万千之力》/《不朽之战》/《主持人核心》/《元素之怒》/《地狱破灭》冒险之路/《大巴扎》/《天夏世界指南》/《天夏角色指南》/《奇人列传》/《学院争霸》/《寻天王冢》/《巨龙圣典》/《怪物核心2》/《怪物核心》/《惊世奇土》/《战吼！》/《旅游指南》/《族裔指南》/《枪械全书》/《核心规则书》/《死亡猎杀》/《死者之书》/《沙尖七灾》冒险之路/《灭绝诅咒》/《灭绝诅咒》冒险之路/《灰烬之年》/《玩家核心2》。
[3] redirect_map 叠加 — 160 个碰撞键中:71 个 redirect_map[X]==''(空目标,resolved='' 查不到 → 回落到被污染裸键),39 个键缺失(直接查被污染裸键),50 个有非空目标(经 redirect 先解析、实际未受害)。有效受害 = 71+39 = 110;其中 107 个在盘上有 pages\<t>.html 且 >5KB(与审计基准 107 精确吻合);1 个无 pages html(酸液（特征）),2 个 ≤5KB。
[4] 构建产物实锤 — pages\武器.html = 105,661 B(真条目)、category\武器.html = 16,304 B;pages\护甲.html 64,395 B、pages\动作.html 89,128 B(同为碰撞键)。扫描 28,514 个 pages\*.html:含 href="../category/%E6%AD%A6%E5%99%A8.html" 且 title="武器" 的受害锚点 4,358 个,分布在 4,125 个文件(样本:8发弹匣.html、T字杖.html、《主持人核心》.html、《天夏世界指南》__创世神话.html);指向 ../pages/武器.html 的锚点 = 0。另有 622 个文件含 title≠"武器" 的 category/武器 链接(页脚 Category:武器,合法,不受影响)。

**Fix spec**

文件:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py,main() 内标题索引循环,行869-879。
将:
```python
    for p in meta.get("pages", []):
        ns = p.get("ns", 0)
        t = p.get("title", "")
        target_dir, bare = determine_target_dir(ns, t)
        title_index[t] = (target_dir, safe_title(bare))
        # also index without ns prefix for short refs (non-clobbering, ns-prioritized)
        if bare != t:
            prio = NS_BARE_PRIORITY.get(ns, 9)
            if bare not in bare_owner_prio or prio < bare_owner_prio[bare]:
                title_index[bare] = (target_dir, safe_title(bare))
                bare_owner_prio[bare] = prio
```
替换为:
```python
    for p in meta.get("pages", []):
        ns = p.get("ns", 0)
        t = p.get("title", "")
        target_dir, bare = determine_target_dir(ns, t)
        title_index[t] = (target_dir, safe_title(bare))
        # Claim the bare key for EVERY page — including colon-less ns0/102
        # titles where bare == t. The priority claim is what blocks a later,
        # lower-priority ns14 "Category:<t>" from clobbering title_index[t]
        # (RC1: 110 article bare-keys were hijacked to category/*.html).
        # When bare == t the full-key write above already holds the correct
        # entry, so we only record ownership without rewriting it.
        prio = NS_BARE_PRIORITY.get(ns, 9)
        if bare not in bare_owner_prio or prio < bare_owner_prio[bare]:
            if bare != t:
                title_index[bare] = (target_dir, safe_title(bare))
            bare_owner_prio[bare] = prio
```
语义:(a) ns0/102 无冒号标题在首次遇到时即以 prio 0/1 占住 bare_owner_prio[t],后到 ns14(prio 4)的 `prio < bare_owner_prio[bare]` 检查失败 → 不再覆写;(b) 若 ns14 先于 ns0 出现(枚举顺序反转),ns0 的全键写入(title_index[t]=pages)天然纠正条目,并以 prio 0 接管所有权,bare==t 时跳过冗余重写;(c) 平 prio 保持先到先得,枚举顺序固定 → 结果确定。
redirect_map 空目标处理:索引修复后无需必改 — rewrite_links 行191 的 `title_index.get('') or title_index.get(target_title)` 回落链自动落到已修复的裸键(71 个空目标键自愈)。可选加固:行188 改 `resolved = redirect_map.get(target_title) or target_title`,使空串目标显式等价于"无重定向",避免空串键将来意外进入 title_index。
预期影响:修复后重跑完整构建(python build_v2.py --redirects),110 个裸键(含 武器/护甲/动作/《核心规则书》等)从 category/ 翻转回 pages/;仅「武器」一键即修正 4,125 个文件中的 4,358 个锚点,110 键合计预计数万锚点级修正。50 个有非空 redirect 目标的碰撞键行为不变;622 个文件的合法 Category:武器 页脚链接不变。
验证命令:重建后 grep pages\*.html 中 `href="../category/%E6%AB%A6%E5%99%A8.html"[^>]*title="武器"`(注意用正确 quote %E6%AD%A6%E5%99%A8)应为 0;`title_index` 模拟脚本(已存 $env:TEMP\rc1_check.py)中 clobbered 应从 160 → 0。

**Risks**

1) 个别键修复后由"错链但活"变死链:酸液（特征） 在 metadata 为 ns0 但盘上无 pages\酸液（特征）.html(parsed 语料缺),修复后指向不存在的 pages 文件;另 2 个碰撞键 pages html ≤5KB(其一 专长.html 仅 450B,是 redirect stub,但 专长 有非空 redirect 目标本就不受害)。建议重建后对 110 键做一次存在性核对。2) 预先存在的边缘缺陷(本修复不引入也不解决):若某页裸键含未识别前缀冒号且恰好等于另一页的全键(如 "Category:Data:x" 的 bare="Data:x" 撞 ns3500 全键),后到的低优先级裸键写入仍可覆写全键;可选加固为预先收集全键集合、裸键写入跳过任何全键成员。本语料 354 个 ns14 标题未发现此类嵌套前缀,实际风险≈0。3) 类别页可达性不受损:category\武器.html 仍可经全键 "Category:武器"/页脚链接到达。4) 重建是全量页面重写(28k+ html),需正常跑完 build_v2.py 全流程;若只 patch 索引不重建,产物不变。5) 审计基准 107 与有效受害 110 的差 3 来自盘上产物状态(1 缺失+2 小文件),非逻辑分歧。

---

### RC2 — status: present

**Evidence**

RC2 完全复现。
【A. 原生富清单页磁盘现状】pages\ 下匹配 列表|总表|索引 共 46 个文件 (C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\)。重点页全部存在,链接数与 RC2 声称完全一致:
- 法术列表.html: 1,307,144 B, <a> 总数 6,985 (main 内 6,893)。页头标注「已重制（2r新版）」=canonical;法术列表（2e）.html (1,403,603 B, 6,257 链接) 为旧版。
- 生物总表.html: 1,604,944 B, 8,756 链接 (main 内 8,664)。
- 诸神总表.html: 688,023 B, 5,142 链接。
- 近战武器列表 333,200 B/1,678 链接;远程武器列表 160,802 B/728;仪式列表 290,629 B/1,432;危害列表 149,020 B/807;戏法列表 187,751 B/979;动物伙伴列表 117,631 B/577 (2r 版,（2e）159,272 B 为旧版);载具列表 109,109 B/546;GM帷幕 27,267 B/170。
- 次级原生清单: 基础护甲列表 84,169 B/385、基础盾牌列表 57,551 B/251、攻城武器列表 81,393 B/429、魔法刺青列表 145,010 B/724、符箓列表 102,537 B/520、圈套列表 137,150 B/734、主题法术列表 148,220 B/600、状态 170,315 B/773、特征 448,309 B/2,403。
- 非目标文件甄别: 武器列表.html (17,425 B)=消歧义页(仅链近战/远程两列表);法术列表__1环~10环+戏法 11 个子页 (~26,352 B 各, main 内仅 12 链接)=未渲染的数据库查询桩,不可作导航目标;护甲列表/盾牌列表/原能法术列表/背景列表/法杖列表等 ~400-540 B 文件均为 redirect 桩 (如 护甲列表→基础护甲列表, 原能法术列表→法术列表)。
【B. 主导航 0 引用核实】对 18 个原生清单页名扫描全部导航面: _snippets\topnav_sub.html (189 行, 0 引用)、_snippets\sidebar_sub.html (33 行, 0 引用)、index.html (仅 GM帷幕 1 处, L839 首页卡片)、search.html 0、browse-*.html 0、classes\index.html 0。即 法术列表(6,985 链)/生物总表(8,756 链)/诸神总表(5,142 链)/武器/仪式/危害/戏法/动物伙伴/载具 等富清单 0 处被主导航链接;玩家分类全指 browse-* 桶: topnav_sub.html L18-21(玩家选项)/L30-37(装备)/L46-54(法术)/L63-69(生物)/L95-96(设定) + 移动镜像 L116-176;sidebar_sub.html L16-29;index.html 内联 topnav L565-753 + 左 rail L775-795 + homenav 卡片 L821-871。
【C. 构建链路】topnav 单一源=_snippets\topnav_sub.html,被 build_v2.py:39/857、build_browse_v2.py:35/364-367(strip ../ 派生 root 版)、build_browse_letters_v2.py:142-143、build_nav_stubs.py:176-177、build_class_hubs_v2.py:22 消费。手工内嵌副本 2 处: index.html L565-753、search.html(已漂移,其生物菜单仍标「怪物」)。首页 homenav 由 pf2wiki-scraper\cat_audit\generate_homenav.py SECTIONS(L15-47) 离线生成后粘贴。

**Fix spec**

原则: 有原生富清单→改指原生页;无原生→保留 browse-*;browse-* 降级为「可排序表格视图」二级入口(去处=侧栏「浏览全部」组原样保留 + topnav 菜单内「浏览:XX(表格)」子项)。规则菜单 8 项(R6)与 信仰→信仰综述/出版物→出版物索引(R8) 一律不动。

【文件1: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\_snippets\topnav_sub.html】(改一处全站生效,需重跑构建)
桌面菜单:
- L17-20 职业/族裔/背景/专长: 不改(无原生清单;背景列表/法杖列表均为 redirect 桩)。
- L21 后新增: <li>动物伙伴 → ../pages/动物伙伴列表.html</li>
- L32 武器 href="../browse-items-weapons.html" → 拆两项: 近战武器 → ../pages/近战武器列表.html;新增 远程武器 → ../pages/远程武器列表.html
- L33 护甲 href="../browse-items-armor.html" → ../pages/基础护甲列表.html;其后新增 盾牌 → ../pages/基础盾牌列表.html
- L34-37 消耗品/穿戴物品/符文/法器: 不改。
- L37 后新增分隔线 + 二级组: 攻城武器→../pages/攻城武器列表.html、载具→../pages/载具列表.html、魔法刺青→../pages/魔法刺青列表.html、符箓→../pages/符箓列表.html、圈套→../pages/圈套列表.html、浏览:武器(表格)→../browse-items-weapons.html、浏览:护甲(表格)→../browse-items-armor.html
- L46 全部法术 href="../browse-spells.html" → ../pages/法术列表.html (标签改「法术列表」);L47 分隔线后新增 浏览:法术(可排序表格) → ../browse-spells.html
- L48-51 奥术/神术/异能/原能: 不改(无原生分传承清单,原能法术列表是 redirect)。
- L53 戏法 href="../browse-spells-cantrips.html" → ../pages/戏法列表.html
- L54 聚能不改;其后新增: 仪式 → ../pages/仪式列表.html、主题法术 → ../pages/主题法术列表.html
- L63 全部生物 href="../browse-creatures.html" → ../pages/生物总表.html (标签改「生物总表」);L64 分隔线后新增 浏览:生物(可排序表格) → ../browse-creatures.html
- L65-69 等级桶: 不改;L69 后新增分隔线 + 危害 → ../pages/危害列表.html
- L78-86 规则菜单: 全部不改(R6 红线);可选增项 L84 勘误索引后: GM帷幕 → ../pages/GM帷幕.html (纯增不改)。
- L95 信仰 href="../browse-deities.html" → ../pages/诸神总表.html (标签「诸神总表」);其前新增 信仰综述 → ../pages/信仰综述.html (R8 语义保留);其后新增 浏览:信仰(表格) → ../browse-deities.html
- L96 地理: 不改。
移动镜像 L113-186: 同步复制以上全部改动(玩家选项 L116-121、装备 L126-132、法术 L138-144、生物 L150、设定 L174-175)。

【文件2: _snippets\sidebar_sub.html】href 零修改 — 「浏览全部」组(L13-31)即 browse-* 可排序表格视图的官方二级入口;仅建议 L14 summary 文案 浏览全部→「浏览(表格视图)」,并可选在其上方加一个折叠组「原生清单」含 6 项: 法术列表/生物总表/诸神总表/仪式列表/危害列表/GM帷幕 (../pages/*.html)。

【文件3: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index.html (手工维护,无生成器)】
- 内联 topnav 桌面 L580-660 + 移动 L678-739: 套用文件1全部改动去掉 ../ 前缀 (关键行: L596-597 武器/护甲、L610 browse-spells.html→pages/法术列表.html、L617 戏法、L627 browse-creatures.html→pages/生物总表.html、L659 browse-deities.html→pages/诸神总表.html、+新增项)。
- 左 rail L775-795: 不改 (rail-count 数字描述的是 browse 桶规模,rail 兼任表格视图入口)。
- homenav 卡片(v0.3.27 设计保留,只改链接/增条目): L826 法术 browse-spells.html → pages/法术列表.html;L837 生物 browse-creatures.html → pages/生物总表.html;L826 后增 <a href="pages/仪式列表.html">仪式</a>;L834 信仰→pages/信仰综述.html 保持(R8),其后增 <a href="pages/诸神总表.html">诸神总表</a>;L839 GM帷幕已原生不动;L821-825/827-828 与 出版物 L845-859、索引与帮助 L861-871 全部不动(R6/R8)。
- 右 rail/热门 L924-952: 不改。

【文件4: search.html】内联 topnav 为漂移旧副本(菜单标签仍是「怪物」): 按文件3同规格修正,或改为从 topnav_sub.html 派生重新生成。

【文件5: C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\cat_audit\generate_homenav.py】SECTIONS L19 ("法术","browse-spells.html")→("法术","pages/法术列表.html");L25 ("生物","browse-creatures.html")→("生物","pages/生物总表.html");L20 后增 ("仪式","pages/仪式列表.html");L28 后增 ("诸神总表","pages/诸神总表.html") — 防止未来重生成回退。

【重建命令】改完 snippet 后依次重跑: python build_v2.py(重嵌 ~24,666 pages+3,646 category)、build_browse_v2.py、build_browse_letters_v2.py、build_nav_stubs.py、build_class_hubs_v2.py。
【预期影响数】topnav_sub.html: 7 处 href 改写 + ~12 增项,×2(桌面+移动)≈38 行级变更;index.html: 内联 topnav 同规模 + homenav 2 改 2 增;search.html 同 topnav 规模;sidebar 0 href 变更;generate_homenav.py 2 改 2 增;规则菜单/出版物/索引与帮助 0 变更(红线全守)。

**Risks**

1) 体积: 法术列表 1.3MB/生物总表 1.6MB/诸神总表 0.7MB,低端设备首屏明显慢于轻量 browse 页;务必保留 browse-* 二级链接作回退。注意维基自身的回退方案(法术列表__N环 分环子页)在离线镜像中是未渲染查询桩(main 内仅 12 链接),不可用作回退,回退只能靠 browse-spells-*。2) 版本陷阱: 必须链无后缀文件(法术列表/动物伙伴列表=2r 重制版);误链（2e）会暴露旧版数据。武器列表.html 是消歧义页,不要直链它,要分链近战/远程两页。3) 手工副本漂移: index.html 与 search.html 的 topnav 是手工内嵌,改 snippet 不会自动同步(search.html 已实证漂移——菜单仍标「怪物」);三处必须同批修改,建议长期改为构建时注入。4) R6 边界: pages\状态.html(170KB/773 链)其实存在,但红线要求 状态→browse-other.html 不回退,本规格不动它——留作未来单独决策。5) rail-count 数字(法术 1,761 等)描述 browse 桶,故左 rail href 不改;若改则数字失真。6) 装备菜单增至 12+ 项,短视口可能溢出,topnav 下拉面板是否有 max-height/滚动未验证,改后需实测 topnav.js 面板;移动端 details 组同样要核对。7) 全量重建触达 ~37k 文件,执行期间勿并发改动;build_nav_stubs.py 会再生成 browse 残桩,确认其数据源未受影响。

---

### RC3 — status: present

**Evidence**

复现确认(语料 C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed\**\*.json, 37,098 文件 / ns0=24,666):
1) 桩计数 = 5,017,与审计基准完全一致。全部由 模板:物品类型数据 生成,措辞 100% 统一:raw parse.text 以 `<div class="mw-parser-output"><p>本页面是存放物品数据的子页面，如果您是通过搜索栏进入本页的，请点击主页面：<a href="/wiki/...” title="父页">父页</a>` 开头。变体分析:存放「物品数据」5,017/5,017,无其他类型;锚定正则 0 near-miss(含"本页面是存放"且<300字的非命中页 = 0)。
2) 父链接:5,017/5,017 含 `<a href="/wiki/..." title="...">`;URL-decode(href[6:]).replace('_',' ') == title 属性 5,017/5,017 → 提取父页用 title 属性即可靠。父页==标题斜杠前缀 4,994/5,017 = 99.54%(23 个不一致均合理,如 龙息符文/龙息（7环法术）→龙息、专家级渔具/专家级渔具→渔具)。父页在 metadata title_index 可解析 5,017/5,017(经 redirect_map 0 个);4 个父页(恐惧×3、白色克莉奥米之眼×1)不在 parsed 语料但 pages\恐惧.html、pages\白色克莉奥米之眼.html 均存在于磁盘(早期构建遗留,见 build_v2.py:923-929 注释)。父页==桩自身标题(刷新死循环风险)= 0。
3) 静态死胡同确认:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\治疗蒸汽__次等治疗蒸汽.html 无 http-equiv="refresh"(render_page_html 仅对 .redirectMsg 页发 meta-refresh,build_v2.py:617-631)。
4) 搜索刷屏确认:index\titles.js 共 37,097 条,5,017/5,017 桩标题全在,types.js 类型码全为 'U';查询样例「治疗药水」命中 6 条 = 5 个指针桩 + 1 个真页(entry 2604/22224/28808/34016/36201 为桩,25306 为真页)。
5) 误伤防护:随机 50 个正则命中逐条人工核验,0 个含指针文本以外内容;最短 20 个未命中 ns0 短页均为「未找到名称匹配的物品：X」类损坏桩(另一问题,不属 RC3)或重定向说明,0 个含「子页面」→ 漏检 0、误伤 0/50。
6) 召回风险量化:480/5,017 (9.6%) 桩的变体名(标题斜杠右段)不在父页标题也不在父页 body[:600](如 迷魂花/紫鸢花、统一徽印/香达郭)。

**Fix spec**

检测正则(已验证 5,017/5,017 命中、0 误伤、0 漏检,对 raw parse.text 锚定匹配):
SUBPAGE_POINTER_RX = re.compile(r'^<div class="mw-parser-output"><p>本页面是存放物品数据的子页面[，,]如果您是通过搜索栏进入本页的[，,]请点击主页面[：:]<a href="(/wiki/[^"]+)"[^>]*title="([^"]+)"')
父页提取:group(2) title 属性(与 URL-decode 后的 href 5,017/5,017 一致)。

【文件 1】C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py — 把指针桩改渲染为带 meta-refresh 的跳转页
(a) 模块级(约 line 113 TEMPLATE_PLACEHOLDER_ENC_RX 之后)加上述 SUBPAGE_POINTER_RX 与计数器 SUBPAGE_POINTER_STATS = {"redirected": 0, "kept_static": 0}。
(b) render_page_html 内,在现有 redirectMsg 分支(line 617-631)之后、`content_html = str(soup)`(line 633)之前插入:
    if not redirect_meta_html and ns == 0 and SUBPAGE_POINTER_RX.match(raw_text.lstrip()):
        parent_a = soup.select_one("div.mw-parser-output > p > a[href]")
        parent_href = (parent_a.get("href") or "").strip() if parent_a else ""
        parent_classes = (parent_a.get("class") or []) if parent_a else []
        if parent_href and not parent_href.startswith("http") and "new" not in parent_classes:
            redirect_meta_html = f'<meta http-equiv="refresh" content="0; url={html_lib.escape(parent_href)}">\n'
            SUBPAGE_POINTER_STATS["redirected"] += 1
        else:
            SUBPAGE_POINTER_STATS["kept_static"] += 1
    要点:raw_text(line 580-581)保留原始 /wiki/ href 供正则检测;soup 此时已过 rewrite_links(line 584),父链已改写为本地相对路径且未知目标带 class="new" → 复用与 redirectMsg 分支(line 626-628)完全相同的 is_dead 防护,父页不存在的桩自动保持原样并计入 kept_static。
(c) main 渲染循环结束后(line 968 附近)打印 SUBPAGE_POINTER_STATS。
预期影响:5,017 页加 meta-refresh 跳父页;当前语料下 redirected=5,017、kept_static=0(全部父页在 title_index 且 4 个 parsed 缺失父页的 HTML 已在磁盘)。

【文件 2】C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py — 把桩剔出搜索索引
(a) 模块级(line 37 STUB_BODY_THRESHOLD 附近)加:
SUBPAGE_POINTER_TXT_RX = re.compile(r"^本页面是存放物品数据的子页面[，,]\s*如果您是通过搜索栏进入本页的[，,]\s*请点击主页面[：:]")
(对 soup.get_text 提取后的 body_text 匹配;已验证桩 body 形如「…请点击主页面： 治疗药水」)。
(b) build() 主循环 line 320 `for ns, pageid, title, body, ...` 之后、line 323 `is_stub = ...` 之前插入:
    if ns == 0 and SUBPAGE_POINTER_TXT_RX.match(body):
        pointer_skipped += 1
        continue
    (循环前初始化 pointer_skipped = 0,line 448 汇总打印加上)。放在 titles.append/type_codes.append/popularity.append 之前,三个平行数组对齐天然保持;entry id 整体重排无碍(每次构建全量重生成)。
预期影响:titles.js 37,097 → 32,080 条;type 'U' 减 5,017;manifest n_stubs 同步下降;「治疗药水」前排只剩真页。search.html/search-app.js 无需改动(索引格式不变)。
可选增强(降召回损失):对 480 个变体名不被父页覆盖的桩,不 continue 而是写入别名条目 {"t": 桩标题, "h": 父页 href, "e": ""}(href 指向父页),其余 4,537 个直接剔除。
验收:重建后抽 治疗蒸汽__次等治疗蒸汽.html 应含 refresh→../pages/治疗蒸汽.html;titles.js 中含「治疗药水」的条目应为 1。

**Risks**

1) 搜索召回损失:480/5,017 (9.6%) 变体名(紫鸢花、香达郭、愤怒魔纹等)剔除后既不在父页标题也不在父页被索引的 body[:600] 内,直接搜该名将搜不到 → 用可选别名方案可消除,代价是保留 480 条指向父页的索引条目。2) 后退按钮:content="0" 的 meta-refresh 使浏览器后退回桩页时立即再次跳转(与现有 build_redirect_stub 跳转桩行为一致,Tauri webview 下可接受)。3) 4 个边缘父页(恐惧、白色克莉奥米之眼)的 HTML 是早期构建遗留;若未来做全量 clean 重建且 parsed 语料仍缺这两页,meta-refresh 会指向 404 —— 该风险与现有 redirectMsg 逻辑完全同构(class="new" 防护只覆盖 title_index 缺失,不覆盖文件缺失),非本修复新增。4) 正则强依赖 模板:物品类型数据 的措辞;若 wiki 未来改模板文案或新增「法术数据」等同类模板,需扩展 [物品数据] 部分(当前语料 100% 单一措辞,已验证无其他变体)。5) 「未找到名称匹配的物品：X」类损坏短桩(另一问题域,见 build_dead_stubs.py)不受本修复影响,刻意不触碰。6) 桩页仍渲染完整页面(保留可见指针文本+链接),仅加 meta-refresh,JS 禁用或 refresh 被拦截时优雅降级为可点击链接。

---

### RC4 — status: present

**Evidence**

【[4b] 现状】C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py L972-1030:仅两条 skip 规则——L1006 跳过已渲染真分类(rendered_cat_names),L1012 跳过分隔符 blob(regex [,;，；] 且不在 metadata ns14 名单)。无 a/b/c 过滤,无孤儿清理。页脚分类条 build_categories_block L419-450:一律渲染蓝链,未知分类 fallback 到 ../category/<safe>.html (L439)。title_index 仅含 metadata 页 (L869-879)。

【磁盘复算 2026-06-10】category\ 共 3,646 个 .html。复现 [4b]:语料 37,097 文件→3,605 个分类反向索引;合成 3,100 + 真抓取 ns14 354 = 期望 3,454;磁盘多出 194 个 = R5 前的分隔符 blob 残骸(R5 只停写未删,样例 category\《拥王者》冒险之路;变种剑子页面.html、专注,情绪,心灵（特征）.html);另 2 个期望名缺失 = NTFS 大小写碰撞 WoI/WOI、WoI子页面/WOI子页面 互覆。

【a 类】严格自指(唯一成员 ns0 且标题==分类名)= 704 个,全部为合成、全部在磁盘、全部出现在 browse-categories.html;与 metadata ns14 交集 = 0(无一是 wiki 真分类);704 个成员目标全部存在于 ns0 语料(meta-refresh 可解析)。提示词的 ~1,495 实为高估:全部单成员合成分类 = 1,337(含 478 个非自指,如 格挡匕首→护法刃);放宽到「（特征）后缀基名匹配」= 859。

【b 类】含「子页面」分类共 583(全部 endswith「子页面」,0 个中缀):合成 420(最大 冒险道具子页面 308 / PC2子页面 244 / BC子页面 232),真抓取 ns14 41 个(物品子页面 5,017 成员、手持物品子页面 等——wiki 真页,须保留);其余 ~122 为 blob 已被 R5 跳过(但磁盘有残骸)。browse-categories.html 含 586 处「子页面」行。

【c 类——关键事实修正】语料 parse.categories 全量 0 个 hidden 字段,但有 missing:true 共 52,970 条、覆盖 3,295 个分类——相关/PC/含有受损文件链接的页面/消歧义 全部 missing:true,即 live wiki 上这些分类页根本不存在(wanted category,页脚显示为红链),并非 hidden category。按模式枚举:相关 2,522(模板簿记)、PC 590(成员全是《玩家核心》法术,书目标签型 wanted cat)、含有受损文件链接的页面 369(MW 维护追踪)、消歧义 116(真分类是已抓取的 消歧义页 206);使用日期魔术字/引用错误/缺失/损坏/失效 = 0 命中;需要翻译 14、消歧义页 206、剧透 1,703 为真抓取页应保留。页脚出现次数:c 类 3,597 页、b 合成 7,113 页、blob 274 页(blob 链接现靠 194 残骸文件苟活,清残骸即死链)。browse-categories.html 共 3,636 行,含全部 704 个 a 类、586 行子页面、4 个 c 类。

**Fix spec**

全部改动在 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py 与 build_browse_v2.py。

【1. 预计算名单】build_v2.py main(),在 [2/4] 反向索引完成后(L912 之后、[4/4] L930 之前)上移 [4b] 的 _ns14_bare 构建块(现 L990-998)并新增:
- MAINT_PSEUDO_CATS = {"相关", "PC", "含有受损文件链接的页面", "消歧义"}(模块级常量);
- BLOB = {cat for cat in category_members if _delim.search(cat) and cat not in _ns14_bare}(194 个);
- B_SYNTH = {cat for cat in category_members if cat.endswith("子页面") and cat not in _ns14_bare}(420 个;endswith 已验证零漏);
- A_SELF = {cat for cat,m in category_members.items() if cat not in _ns14_bare and len(m)==1 and m[0][1]==0 and m[0][2]==cat}(704 个);
- PAGELESS_CATS = BLOB | B_SYNTH | MAINT_PSEUDO_CATS(修复后无页面的分类)。

【2. 页脚分类条】build_categories_block (L419) 增参 pageless_cats: set;L434-442 改为:if display in pageless_cats → items.append(f'<li><span class="new">{html_lib.escape(display)}</span></li>')(不产链接,仿 MW 红链降级为带 .new 样式纯文本;assets\style.css 加 .page-categories .new{color:#ba0000} 之类);否则原逻辑。render_page_html (L566) 与两处调用 (L652、[4b] fake 渲染 L1021) 透传该集合。影响 ~10,984 处页脚条目(3,597+7,113+274)。a 类不入 pageless(stub 文件存在,链接照常,点击即跳成员页)。

【3. [4b] 循环】L1001-1028 在 blob skip 之后加:
- if cat in B_SYNTH or cat in MAINT_PSEUDO_CATS: n_skip_bk += 1; continue(共 424 个不再合成);
- if cat in A_SELF: 不走 render_page_html,直接写极简 meta-refresh stub 到 category/<safe_title(cat)>.html,target = f"../pages/{urllib.parse.quote(safe_title(member_title)+'.html')}"(成员 100% 在 ns0 语料;可仿 build_redirect_stub 的 HTML 骨架),704 个;
- else 原样全 chrome 合成(1,972 个)。

【4. 孤儿清理】[4b] 结束处(L1029 后,仅全量构建分支)新增 sweep:expected_stems = {safe_title(c) for c in rendered_cat_names} | {本轮 [4b] 实际写出的 stem};遍历 (ROOT/"category").glob("*.html"),stem 不在 expected_stems(用 casefold 比较,防 WoI/WOI 误删)即删除并计数。预期删除 618 = 194 blob 残骸 + 420 b 类 + 4 c 类。此 sweep 仅限 category\(354 个真 ns14 全在语料、每轮全量重写,安全;不可推广到 pages\,见 L923-929 注释)。

【5. browse-categories】build_browse_v2.py L424-431 cat_entries 组装循环加排除:跳过 cat 若 (a) cat.endswith("子页面")(含 41 个真分类一并剔出列表,真页仍可经页脚到达;若想保留真页行,改为仅剔非 ns14_titles 者,少剔 41 行);(b) cat in MAINT_PSEUDO_CATS;(c) _delim.search(cat) 且非真 ns14;(d) len(cat_to_entries.get(cat,[]))==1 且唯一 entry.title==cat 且非真 ns14。预期行数 3,636 → ~2,344(−704 a −586 子页面 −4 c +少量交叠)。

【预期影响数】category\ 文件:3,646 → ~3,028(354 真抓取 + 1,972 全 chrome 合成 + 704 meta-refresh stub − 2 大小写碰撞);其中删 618、降级为 stub 704。页脚:~10,984 条目由蓝链降为 .new 纯文本。browse-categories:剔 ~1,294 行。

**Risks**

1) 前提修正:c 类在 live wiki 不是 hidden category(语料 0 hidden 字段)而是 missing:true 的 wanted category,live 页脚显示为红色编辑链;离线降级为 .new 纯文本是最贴近的保真处理,但严格说 live 上点红链可见空分类的成员列表——若追求该行为,c 类可改留极简成员页而仅从 browse 剔除。2) "PC"(590) 实为《玩家核心》书目标签 wanted cat(成员全是 PC 法术),非纯维护;降级会损失一个可用的书目成员列表,如不接受可将其移出 MAINT_PSEUDO_CATS(全 chrome 合成 +1,删除 −1)。3) "消歧义"(116) 与真分类"消歧义页"(206) 成员集不同,不可简单 meta-refresh 合并,纯降级最安全。4) 41 个真抓取「子页面」分类(物品子页面 5,017 成员等)绝不可删/跳——[4b] 循环天然只处理未渲染分类故安全,但 browse 剔除与孤儿 sweep 都必须以 rendered_cat_names 为白名单。5) 孤儿 sweep 必须 casefold 比较且仅限 category\ 全量构建:WoI/WOI、WoI子页面/WOI子页面 在 NTFS 互覆,精确字符串比较会把活文件当孤儿删掉;且 pages\ 语料(37k)小于 metadata(40k),同类 sweep 推广过去会重蹈死链 1.7%→10.5% 的覆辙(build_v2.py L923-929)。6) a 类 stub 在成员页自身页脚点击会自跳回原页(自环),无害但可感知。7) 478 个单成员非自指合成分类与 859−704=155 个「（特征）基名匹配」候选不在本次清理范围,仍是全 chrome 页;如后续扩大 a 类规则需另行决议。8) 页脚降级依赖 PAGELESS_CATS 在 [4/4] 渲染前算好——实现时注意名单计算必须先于内容页渲染(本 spec 已把计算点放在 L912 后)。

---

### RC6 — status: present

**Evidence**

【RC6 复现确认】
1) 根首页是自造壳、非脚本产物:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index.html(963 行,手工维护)。全部 5 个构建脚本均不写根 index.html(build_v2.py 仅在 L410 引用 "../index.html";写盘点只有 L954/L1027/L1057,均为 pages/分类/stub)。唯一相关生成器是 C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\cat_audit\generate_homenav.py(L16-49 SECTIONS,只产出 homenav 片段到 out_v2\_cat_audit\_homenav.html,需手工粘回 index.html)。
2) 根 index.html 丢弃的维基首页策划块(ground truth: pages\首页.html 37,330B;语料 out_v2\parsed\85\6ff361e869cb31d46f27b17deb48df21699783.json title=首页 ns=0 parse.text=18,168 字符):
   - 跑团工具 6 个外部工具(首页.html L324-329):PF2 Tools→https://pf2.tools/;Pathbuilder2e→https://pathbuilder2e.com/;Foundry VTT→http://foundryvtt.com/;Scribe Tool→http://scribe.pf2.tools/;Monster Tool→http://monster.pf2.tools/;PF2 Easy Tool→http://pf2easy.com/。根 index.html 外链总数=0(grep 'href="http' 0 命中)→ 全部缺失。
   - PAIZO动态外链(L277-279):paizo.com/community/blog、paizo.com/paizo/press、45.79.87.129 bbs 4 个 playtest 帖 → 缺失。
   - 特色词条(L331-337):塔-巴丰 + 简介 + 配图 images/a6/14e65371608d7aef86d5c78b925f8ad4ebd179.jpg(磁盘存在,目标页 pages/塔-巴丰.html 存在)→ 缺失。
   - 编辑指南(L339-357):维基任务→project/任务.html(存在,根缺失);需要帮助页面→category/需要帮助.html(存在,根缺失);译名表→pages/术语索引.html(根已有"术语索引",标签不同);帮助中心→category/帮助.html(根已有);bug反馈表 docs.qq.com 外链与 6 个帮助_* 红链(pages/帮助_编辑页面.html 等磁盘 MISS,维基上也是 class="new" 红链)→ 不应补。
   - 跑团活动(L311-316):QQ群 695214825 文本、角色扮演游戏是什么?(根已有"新手入门")、《玩家核心》(根已有)。
   - 已镜像块:新书发布/即将发布→根"出版物"区;玩家手册 8 格→"规则导航";世界设定 8 格→"世界设定";本站索引→"索引与帮助";最新公告/最近编辑/最近评论 = huiji 动态 embed,离线不可用,根用"本镜像数据"替代,合理。
3) pages\首页.html 孤立性:全站 37k+ HTML 中指向 pages/%E9%A6%96%E9%A1%B5.html 的文件仅 6 个 — browse-CJK.html(3.4MB 字母平铺表 1 个链接)+ 5 个本身不可达的边缘页(pages/首页__近期评论.html、活动首页.html、Bootstrap_Subnav.html、测试首页2.html、测试首页3.0.html);browse-categories.html 链的是 category/首页.html(分类页,非本页)。根 index.html 引用数=0。策划导航层面 0 入链,实质孤立。
4) pages\首页.html 渲染质量:topnav 在(L29-213)、面包屑(L219)、sidebar(L221-252)、footer 在;内链已重写为本地、图片本地化(banner images/07/2aff…jpg 存在)。但布局降级:其标记用的 Tailwind 类 grid/grid-cols-1/sm:grid-cols-3/sm:col-span-2/gap-4/order-*/p-4/flex/text-center/font-bold 及维基自定义 grid-main/grid-cell/grid-text/grid-helper 在 assets\*.css 全部无定义(_v2_compat.css §8a 只有 flex-1/flex-col/items-center/justify-between/gap-1/my-2/ml-4/pl-2/w-full/w-1\/10;wiki_native.css 的 .flex 只是 smw spinner)→ 三栏塌成单列、图格纵向堆叠;L360-364 的 huiji-bloglistembed 永远显示"正在加载博客列表..."、activityembed/commentembed 空框。
5) external_links.js 已在根 index.html L557 加载(Tauri invoke('open_external') 打开系统浏览器,isExternal() 接受 http/https 含 IP 字面量)→ 新增外链卡片无需额外接线。

**Fix spec**

【全部修改点(只读审计,未执行)】目标文件 3 个,预期影响:index.html 4 个插入点 + generate_homenav.py 1 处同步 + _v2_compat.css 追加 ~35 行;新增外链 6(+2 可选)、新增内链 5,全部目标磁盘已核实存在。

A. C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index.html(手工维护文件,直接编辑,无构建覆盖风险)
A1.「维基原版首页」入口 ×2:
  - L869(`<a href="category/帮助.html">帮助</a>`)后插入:
    <a href="pages/首页.html">维基原版首页</a>
  - L945(关于 rail `分类索引` li)后插入:
    <li><a class="rail-link" href="pages/首页.html"><span class="rail-label">维基原版首页（存档快照）</span></a></li>
A2. 跑团工具 6 外链 rail 卡片 — L939(`<div class="rail-group rail-about">`)前插入:
    <div class="rail-group">
      <h3 class="rail-head">跑团工具（外部网站）</h3>
      <ul class="rail-list">
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://pf2.tools/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">PF2 Tools · 数字化工具</span></a></li>
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://pathbuilder2e.com/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">Pathbuilder2e · 数字化车卡</span></a></li>
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://foundryvtt.com/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">Foundry VTT · 跑团平台</span></a></li>
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://scribe.pf2.tools/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">Scribe Tool · 规则排版</span></a></li>
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://monster.pf2.tools/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">Monster Tool · 怪物自定义</span></a></li>
        <li class="rail-li rail-li-other"><a class="rail-link" href="https://pf2easy.com/"><span class="rail-dot" aria-hidden="true"></span><span class="rail-label">PF2 Easy · 简单查询</span></a></li>
      </ul>
    </div>
  (外链由已加载的 assets/external_links.js 自动接管;可选在该组末尾追加 paizo.com/community/blog、paizo.com/paizo/press 两条 PAIZO 动态链。)
A3. 特色词条卡片 — L872(homenav `</section>`)与 L874(`<section class="recent"`)之间插入:
    <section class="recent" aria-label="特色词条">
      <h2 class="section-h">特色词条</h2>
      <div class="recent-body">
        <p><a href="pages/塔-巴丰.html"><strong>塔-巴丰</strong></a> — 无数的书籍记录着塔-巴丰和他不断增加的遗产。他曾是异常骄纵而有天赋的学生,受末位暴食符文领主诱惑,在恐惧之岛挖出直达负能量位面的传送门,与神明奥罗登长期竞争,终堕巫妖之道。 <a href="pages/塔-巴丰.html">阅读全文 →</a></p>
      </div>
    </section>
A4. 索引与帮助 nav-grid 补 2 链 — L869 后(与 A1 同点)追加:
    <a href="project/任务.html">维基任务</a>
    <a href="category/需要帮助.html">需要帮助页面</a>
  (帮助_编辑页面 等 6 个编辑红链与 docs.qq.com bug反馈表不补:磁盘 MISS/离线无意义。)

B. C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\cat_audit\generate_homenav.py — SECTIONS"索引与帮助"列表(L44-49)同步追加,防止将来重生成片段回贴时丢失:
    ("维基任务", "project/任务.html"), ("需要帮助", "category/需要帮助.html"), ("维基原版首页", "pages/首页.html"),

C. C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css — §8a(L1332 起)追加首页渲染修复(规则按 body.page-首页 限定作用域,避免污染其他页):
    body.page-首页 .mw-parser-output .grid{display:grid}
    body.page-首页 .mw-parser-output .grid-cols-1{grid-template-columns:1fr}
    body.page-首页 .mw-parser-output .gap-4{gap:1rem}
    body.page-首页 .mw-parser-output .flex{display:flex}
    body.page-首页 .mw-parser-output .p-4{padding:1rem}
    body.page-首页 .mw-parser-output .text-center{text-align:center}
    body.page-首页 .mw-parser-output .font-bold{font-weight:700}
    body.page-首页 .mw-parser-output .overflow-hidden{overflow:hidden}
    body.page-首页 .mw-parser-output .max-h-\[500px\]{max-height:500px}
    @media(min-width:640px){
      body.page-首页 .mw-parser-output .sm\:grid-cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
      body.page-首页 .mw-parser-output .sm\:col-span-2{grid-column:span 2/span 2}
    }
    body.page-首页 .mw-parser-output .grid-main{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px;padding:8px}
    body.page-首页 .mw-parser-output .grid-cell{position:relative;text-align:center}
    body.page-首页 .mw-parser-output .grid-cell img{width:100%;height:auto;display:block;border-radius:4px}
    body.page-首页 .mw-parser-output .grid-text{position:absolute;inset:auto 0 0 0;background:rgba(0,68,22,.78);color:#fff;font-weight:700;padding:2px 0}
    body.page-首页 .mw-parser-output .grid-helper{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:8px}
    /* 离线死区:隐藏 huiji 动态 embed 及其外层公告/编辑/评论框 */
    body.page-首页 .mw-parser-output div:has(>div>.huiji-bloglistembed),
    body.page-首页 .mw-parser-output div:has(>div>.huiji-activityembed),
    body.page-首页 .mw-parser-output div:has(>div>.huiji-commentembed){display:none}
  (页面 body class 已含 page-首页,首页.html L24 已核实;:has() 在 Tauri WebView2/Chromium 可用。)

【目标页存在性核实(全 OK)】pages/首页.html、pages/塔-巴丰.html、project/任务.html、category/需要帮助.html、category/帮助.html、pages/角色扮演游戏是什么？.html、pages/术语索引.html、images/a6/14e65…d179.jpg、images/07/2aff…63b.jpg;MISS(故不补):pages/帮助_编辑页面.html、pages/帮助_常用模板.html 等编辑红链。

**Risks**

1) index.html 无构建脚本回写,手工编辑安全;但 generate_homenav.py 重生成的 homenav 片段若再次手工回贴,会覆盖 A4 在 homenav 内的新增 → 必须同步 B 项,A2/A3 在 homenav 区块之外不受影响。2) pages/首页.html 是冻结快照(日期 AD 2026/5/19、新书时效、45.79.87.129 论坛 IP 链接可能腐烂)→ 入口文案标注"存档快照"管理预期。3) 维基原文 4 个工具外链是 http://(foundryvtt/scribe/monster/pf2easy),规格升级为 https;若有站点不支持 https 会打不开,可回退原 scheme(external_links.js 两者都放行)。4) CSS 修复若不加 body.page-首页 作用域,.grid/.p-4/.flex 等通用名会改变其它含同名类页面的布局(全站 Tailwind 类用例极多);按规格限定作用域则零外溢,代价是其他同样用这些类的页面(如 活动首页/测试首页)仍保持降级。5) :has() 隐藏死 embed 依赖 Chromium ≥105(WebView2 满足);若需兼容更老内核,改为只隐藏 .huiji-*embed 本体,会残留绿色标题条空框。6) 特色词条为静态摘录(live 维基会轮换),内容固定为塔-巴丰;摘要文字按版面可再压缩。7) browse-CJK/测试页等 6 个既有入链不受本修复影响;category/首页.html 链接的是分类页,勿与条目页入口混淆。

---

### RC7 — status: partial

**Evidence**

扫描 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2 全部 44,095 个 HTML:含 http-equiv="refresh" 共 3,618 个(3,614 个 bare stub 由 build_v2.py build_redirect_stub 生成 + 4 个完整渲染页带 redirect_meta: pages\TiG.html、pages\《猛虎觉醒》.html、pages\元素使.html、pages\魂铸者.html)。

[1] 多跳:实测 23 条链,全部恰好 2 跳,0 条 3-4 跳(声称的 ~45 个 2-3 跳 + 5 例 4 跳不成立)。跳数分布 {1跳: 3,595, 2跳: 23}。23 条链全部是「X（特征）→X→X特征」模式(发射（特征）→发射→攻城武器 例外),完整清单:休整/双手/发射/固守/塑法/多用/夺命瞄准/夺命/弹容/投掷/拆毁/散射/易藏/模块化/添加剂/火焰/类人/致命/远射/金/长触及/附着/骑战,均位于 pages\。
根因(build_v2.py):redirect_map["X（特征）"]="" 空目标(metadata.json 5,799 条 redirect 中 2,226 条空目标)→走 _resolve_redirect_target 启发式(L754-794):候选顺序把裸 base「休整」排在「休整特征」之前(L762-767),且 L789 `if c in title_index: return c` 命中后既不沿 redirect_map 继续追链、也不验证该候选真有渲染页。「休整」在 title_index 里只因 metadata.json pages 列出它,但 37,097 个 parsed JSON 中无「休整」(幽灵条目);磁盘上 pages\休整.html 本身是 441B 的旧 stub→2 跳。

[2] 自指无限刷新:不可复现。3,618 个 refresh 文件中自环 0、多文件环 0、目标缺失 0。pages\任务__首页推送.html→project\任务__首页推送.html(跨目录、真页),pages\博客.html→category\博客.html(真页);L822-824 的同目录同名 guard 已拦截真自指。

[3] 闪屏:成立。3,614 个 bare stub 仅 meta-refresh,正文「正在跳转到…」可见一帧;4 个完整渲染重定向页还加载全套 CSS/JS 后才刷新,闪屏最重。

[附带发现(影响修复方案)] L1042 `src in existing_titles` 用 metadata 标题集判「已是真页」,但 3,662 个 metadata 标题无 parsed JSON(幽灵),其中 3,569 个是 redirect 源:当前构建对它们既不渲染页也不写 stub,全靠旧构建遗留的磁盘 stub(3,569 个全部在盘上)兜着;干净目录重建会产生 3,569 个 404,且 23 个（特征）stub 将指向不存在的文件。

**Fix spec**

全部改动在 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py。

(0) 收集真实渲染标题集 rendered_titles:在 main() 的 [2/4] 分类预扫描循环(L890 起,已逐个读取全部 parsed JSON)顺手收集 `rendered_titles.add(doc.get("title",""))`;若 args.limit 非 0 则跳过下述基于 rendered_titles 的校验(避免局部构建误判)。

(i) 构建时折叠到终端真页 — 改 _resolve_redirect_target (L726-794),新签名追加 rendered_titles 参数:
```python
def _chase(start: str, redirect_map: dict, limit: int = 10) -> tuple[str, bool]:
    """Follow redirect_map from start; returns (final, hit_cycle)."""
    seen: set[str] = set()
    cur = start
    while cur and redirect_map.get(cur) and cur not in seen and len(seen) < limit:
        seen.add(cur)
        cur = redirect_map[cur]
    return cur, (cur in seen)
```
候选循环 L784-794 改为:对每个候选 c 先 `final, cyc = _chase(c, redirect_map)`;cyc 为真或 final == src_title → 跳过该候选;接受条件改为 `final in rendered_titles`(替代 `c in title_index`),下划线变体同理。效果:「休整（特征）」候选「休整」被追链到「休整特征」(已渲染)→ stub 直指 ../pages/休整特征.html,23 条 2 跳链全部归 1 跳;「发射（特征）」直指 攻城武器.html。环/自指落入现有 None 返回路径(n_unresolved/n_self,不写 stub)。

(ii) 幽灵源修复 — L1035 `existing_titles` 改用 rendered_titles 构建(或 `existing_titles &= rendered_titles`),L811 同一集合自动生效。预期 +3,569 个幽灵 redirect 源恢复显式生成 stub(目标经 _chase 折叠),干净重建不再 404。

(iii) 消闪屏 — 两处模板加同步 script 跳转(WebView2 必启 JS;location.replace 不污染历史栈;meta-refresh 留作兜底):
A. bare stub 模板 L827-837 替换为:
```python
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-Hans">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<script>location.replace({json.dumps(redirect_url)});</script>\n'
        f'<meta http-equiv="refresh" content="0; url={redirect_url}">\n'
        f'<link rel="canonical" href="{redirect_url}">\n'
        f'<title>{html_lib.escape(src_title)} — 跳转至 {html_lib.escape(final)}</title>\n'
        '</head>\n<body>\n'
        f'<p>正在跳转到 <a href="{redirect_url}">{html_lib.escape(final)}</a>...</p>\n'
        '</body>\n</html>\n'
    )
```
B. 完整页 redirect_meta_html L629-631 替换为:
```python
            redirect_meta_html = (
                f'<script>location.replace({json.dumps(redirect_target)});</script>\n'
                f'<meta http-equiv="refresh" content="0; url={html_lib.escape(redirect_target)}">\n'
            )
```
(json 已在文件顶部 import;json.dumps 给出带双引号的 JS 字符串字面量,URL 经 percent-encode 无 `</script`/`<` 风险;script 内不要再 html-escape。)redirect_meta_html 在 L667 注入于样式表之前,同步执行先于首帧绘制。

预期影响数:2 跳链 23→0;3,618 个 refresh 文件全部获得无闪屏 script 跳转;干净重建下 3,569 个幽灵源恢复 stub 覆盖;自指/环维持 0(新增 _chase visited-set 对 map 级环防护)。验证:重建后重跑扫描脚本(本次审计脚本逻辑:解析每个 refresh 目标→映射磁盘→追链),期望分布仅 {1: ~3,618+3,569},多跳/自环/缺失均为 0。

**Risks**

1) rendered_titles 校验依赖全量 parsed 预扫描:--limit 局部构建时必须退回旧行为(只查 title_index),否则大量候选被误拒。2) 追链改变 stub 目的地:只有「候选本身是 redirect 源或幽灵」的 stub 会改目标(精确 23 个 + 3,569 个幽灵源),真渲染页候选不受影响;但若某 redirect_map 目标既是真渲染页又是 redirect 源(本语料未发现),折叠会跳过中间真页——与 wiki 原生双重重定向行为一致,可接受。3) json.dumps 注入 script:勿对 script 行做 html_lib.escape,否则 &quot; 破坏 JS;URL 含 `</script>` 子串理论上可破壳,但 redirect_url 经 urllib.parse.quote、redirect_target 来自 soup href(percent-encoded),实测语料无此风险。4) location.replace 后退体验:用户从 A 点链接进 stub 再后退会回到 A(replace 不留历史),符合预期;若改用 location.href 会产生后退死循环——必须用 replace。5) 构建不清理 pages/(L923 注释为有意为之):23 个旧 2 跳 stub 与 3,569 个幽灵 stub 文件名不变、原地覆盖,无孤儿文件;但另有 93 个幽灵标题不在 redirect_map 中,站内链接指向它们仍靠旧文件兜底,属 RC7 之外的独立问题。6) 4 个完整渲染重定向页(TiG 等)在 JS 禁用环境仍闪一次(meta 兜底),Tauri/WebView2 内不发生。

---


## 核查通过的新发现

### [css/CF1-image-anchor-nuke] P0 — build_v2.py rewrite_links() 把 <a class="image"><img></a> 整体删除 — 13.2% ns0 页面的全部链接式图片(怪物肖像/缩略图/导航盒封面)在构建产物中消失

**Evidence**

审计 monster-portrait 类(零 CSS 规则, 全语料 1,278/24,666=5.18% ns0 页)时发现其在 6,000 个 built 页面中出现 0 次。根因: build_v2.py L177-184, 任何 href 以图片扩展名结尾的 <a> 被 a.replace_with(a.get_text()) 替换, 而 MediaWiki 图片嵌入结构 <a href="/wiki/文件:X.webp" class="image"><img ...></a> 的 get_text()="" → 锚点连同内部 <img> 整体被删; 且 rewrite_links(L584) 先于 rewrite_images(L585) 执行。实锤: pages/叛教尸.html — 语料 parsed/05/18c246bbbb0f8e694af84064426f13c6367c62.json 含 <img class="monster-portrait" width=711 height=1024 src=...Herexen.webp...>, built 页对应位置只剩 <p>\n</p>; pages/黛丝娜.html — 5 个 <div class="thumbinner" style="width:302px"> 全部只剩空 thumbcaption, thumbimage 出现 0 次。规模(随机 2,000 ns0 抽样): 264 页(13.2%)共 797 个锚包图片被删, 外推全站 ~3,300 页 / ~9,800 图。可恢复性: 抽样 1,500 页中 635/635 (100%) 被删图片的文件名都能在 out_v2/images/manifest.json (3,403 条)命中, 本地图片完整, 仅需改构建器+重建。受牵连类: monster-portrait(5.18%), navbox-image 封面(1.81%), thumbimage(1.18%)。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\叛教尸.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\黛丝娜.html; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\images\manifest.json

**Fix spec**

build_v2.py L181-184 改为: 命中图片扩展名分支时, 若 a.find('img') 存在则 a.unwrap()(保留子节点, 让 L585 的 rewrite_images() 正常本地化 src 或打 v2-missing-image 标记——该 fallback 样式已存在于 _v2_compat.css:467), 仅当锚点内无 <img> 时才 a.replace_with(a.get_text())。改后全量重建 pages/。

**Verifier note**: CONFIRMED P0, independently reproduced with a different random seed. (1) Code: build_v2.py L181-184 — any <a> whose unquoted /wiki/ target matches \.(png|jpg|jpeg|gif|webp|svg|bmp|ico)$ gets a.replace_with(a.get_text()); for MediaWiki image embeds <a href="/wiki/文件:X.webp" class="image"><img></a> get_text()=="" so anchor+img are deleted entirely; rewrite_links (L584) runs before rewrite_images (L585) so the img never reaches localization. (2) Spot examples: corpus parsed/05/18c246bbbb0f8e694af84064426f13c6367c62.json (叛教尸, ns0) contains <a class="image"><img class="monster-portrait" ... Herexen.webp></a>; built pages/叛教尸.html has exactly '<p>\n</p>' at that position, monster-portrait count 0; pages/黛丝娜.html has 5 thumbinner divs with 0 thumbimage. (3) Scale (my seed=123): 24,668 ns0 parsed docs (37,098 total); random 2,000 sample → 264 pages affected (13.2%, exact match) with 819 anchor-wrapped image links (claim 797, same magnitude); extrapolation ~3,256 pages / ~10,102 images. (4) Built verification: 60 affected pages → 182/182 image filenames absent from built HTML, 0 survivors. monster-portrait: 1,278 corpus files (exact match to claim) vs 0 occurrences across ALL built pages/ (rg). (5) isOurs: corpus (ground truth) has the images intact — this is purely a build-layer deletion, not wiki-inherent. (6) Fixable without rescrape: images/manifest.json has 3,403 entries (exact match); all 239 unique deleted filenames from my sample hit the manifest via lookup_manifest key variants (100%), and 80/80 spot-checked entry['local'] files exist on disk under out_v2/images/. Proposed fix (a.unwrap() when a.find('img') exists, else keep replace_with(get_text())) is sound: unwrap preserves the <img> for rewrite_images() at L585, which already has a v2-missing-image fallback. Requires only build_v2.py change + full pages/ rebuild. Files: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py (L136-213, L373-403, L584-585); C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\叛教尸.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\黛丝娜.html; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\images\manifest.json.

---

### [css/CF2-wiki-native-css-404-capture] P1 — wiki_native.css 第 3、4 节是 404 HTML 而非 CSS — site.styles(Common.css)层从未被捕获; Tailwind 经 JS loader 加载也未捕获(RC5 根因); cite 等模块因单样本页偏置缺失

**Evidence**

assets/wiki_native.css (400,013 字符)由 fetch_native_styles_v2.py 从单一样本页(战士)的 4 个 <link rel=stylesheet> 拼接。逐节检查: 第 3 节(ext.gadget.Ihover.css|gallerygrid, 23,616 字符)与第 4 节(site.styles, 24,317 字符)开头均为 '<!DOCTYPE html>...<title>MediaWiki:404 - 灰机wiki' — 抓取时返回 404 HTML 被原样塞进 CSS 文件(花括号恰好平衡 46/46、48/48, 未截断后续解析, 但 ~48KB HTML 垃圾混入级联)。后果: (a) MediaWiki:Common.css 站点层整体缺失 — .statblock/.quote-block 等只存在于手写 _components.css/pf2_theme.css/_v2_compat.css, 凡未手工回填的站点类全部零规则(见 CF3/CF4); (b) 404 页内 RLPAGEMODULES 含 'ext.huiji.TailwindCSSLoader' — 证明 Tailwind 工具类经 JS 注入、link 抓取永远抓不到, 即 RC5 (.flex) 一族缺口的机制性根因; (c) 样本页(战士)无参考文献 → ext.cite 样式模块不在其 link 模块表里 → references-column-count* 等零规则(见 CF6)。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\wiki_native.css; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\fetch_native_styles_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_native_sample_page.html

**Fix spec**

短期: 从 wiki_native.css 删除两段 404 HTML(以 '/* ==…load.php?…Ihover…*/' 与 '/* ==…site.styles…*/' 节头定位, 共 ~48KB)。中期(待网络可达时重跑): fetch_native_styles_v2.py 增加 (1) 响应体以 '<!DOCTYPE' 开头或 Content-Type 非 text/css 时报错重试而非写入; (2) 单独抓 /load.php?modules=site.styles&only=styles 与 ext.cite.styles; (3) 解析 TailwindCSSLoader 注入的 CSS URL 并抓取。在此之前继续按 _v2_compat.css §8 手工回填(CF3-CF5 给出具体规则)。

**Verifier note**: 复现成立。wiki_native.css 恰为 400,013 字符(声称值精确匹配),含 4 节,对应 _native_sample_page.html(战士样本页,fetch_native_styles_v2.py:29 硬编码)的 4 个 <link rel=stylesheet>。第 3 节(ext.gadget.Ihover.css|gallerygrid,偏移 351,617)与第 4 节(site.styles,偏移 375,482)正文各 23,616 字符、字节级完全相同,均以 '<!DOCTYPE html>' 开头、<title>MediaWiki:404 - 灰机wiki…</title>,花括号均 46/46 平衡(原发现称第 4 节 24,317 字符/48 对,属小误差,不影响结论;两段垃圾共 ~47.2KB ≈ 声称的 ~48KB)。机制确认:fetch_native_styles_v2.py:159 仅检查 status_code!=200,无 Content-Type/响应体校验,404 页以 HTTP 200 返回即被原样写入。后果逐项复现:(a) statblock/quote-block/references-column-count/mw-references 在 wiki_native.css 中零出现,仅靠手写层回填(statblock 见 _components.css/pf2_theme.css/_v2_compat.css,quote-block 仅 _v2_compat.css);影响面大——抽样前 6,001 个构建页中 3,240 页(54%)含 class="flex flex-col quote-block statblock my-2"(同一元素同时踩中缺失的站点类与 Tailwind 工具类),references-column-count 见于 43/6,001 页;(b) 样本页 RLPAGEMODULES 含 ext.huiji.TailwindCSSLoader 且无 Tailwind <link>,wiki_native.css 中裸 .flex 规则缺失(仅有 .smw-overlay-spinner.flex 复合选择器,偏移 ~31,918)——RC5 机制性根因成立;(c) 战士样本页 0 个 cite_note 锚点、RLPAGEMODULES 无 ext.cite,单样本偏置成立。垃圾确实全站下发:每页 → ../assets/style.css → @import wiki_native.css。isOurs=true:live wiki 对浏览器返回真实 CSS,存入 404 HTML 是我们抓取层无内容校验所致,缺 Tailwind/site.styles 也是 link-only+单样本抓取方法的缺陷,非 wiki 固有。fixableWithoutRescrape=true 但有保留:删除两段 404 HTML(按两节头注释定位,共 ~47.2KB)纯离线可做;缺失样式按 _v2_compat.css §8(8a-8k 已存在)继续手工回填也离线可做;但 site.styles/Common.css 的真实源码离线不可恢复——metadata.json 40,736 页清单中 MediaWiki 命名空间为 0 条(仅 Manifest:Ihover.css 一个标题,且 parsed 目录无对应文件),完整保真恢复(site.styles、Tailwind 注入表、ext.cite.styles)仍需网络可达后重跑增强版抓取脚本。涉及文件:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\wiki_native.css、C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\fetch_native_styles_v2.py、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_native_sample_page.html、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\style.css。

---

### [css/CF3-monster-portrait-zero-rule] P2 — .monster-portrait 零规则 (5.18% ns0 页) — CF1 修复恢复肖像后将以原始 711-1000px 宽度撑满正文列, 压垮怪物 statblock 版面

**Evidence**

全语料 1,278/24,666 (5.18%) ns0 页含 class="monster-portrait"(全部怪物条目, 例: 至古圣天龙/二性修罗/叛教尸)。结构: <p><a class="image"><img class="monster-portrait" width=711 height=1024></a></p> 紧插在特征 tag 行与察觉行之间。12 个 assets/*.css 中无任何 .monster-portrait 选择器(原样式在未捕获的 site.styles 层, 见 CF2)。当前被 CF1 整体删除; CF1 修复后, 级联里仅 wiki_native.css 的 img{max-width:100%} 兜底 → 肖像以正文列全宽渲染插在 statblock 第一行, 与原生 wiki 的受约束肖像呈现严重偏离。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed\05\18c246bbbb0f8e694af84064426f13c6367c62.json

**Fix spec**

随 CF1 一并落地, 在 _v2_compat.css §8a (L1332 起)追加: .mw-parser-output img.monster-portrait { float: right; max-width: min(40%, 320px); height: auto; margin: 0 0 .5em 1em; } /* 注: 数值为离线重建(live Common.css 不可达), 待 CF2 重抓 site.styles 后用真值校正 */

**Verifier note**: 复现成功,数字完全吻合。方法:temp 脚本全量扫描 C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed (37,098 json) → 1,278/24,666 ns0 页 (5.18%) 含 class="monster-portrait",非 ns0 为 0;引用样例 (叛教尸, parsed\05\18c246...json) 结构与声称一致 (特征行→<p><a class="image"><img class="monster-portrait" 711x1024></a></p>→察觉行),且 1,271/1,278 (99.5%) 肖像紧邻察觉行,确在 statblock 首部。12 个 assets\*.css 逐一 grep,.monster-portrait 选择器 0 命中;wiki_native.css 头部 load.php 模块清单仅含扩展/皮肤样式 (无 site.styles),证实 live Common.css 层未捕获。一处低估:实际肖像原始宽度达 1500px (1500px×122 页, 1159px×56, 1000px×96),比声称的 711-1000px 更宽,问题更重。潜在效应链亦验证:当前 build_v2.py L179-184 把指向图片扩展名标题的 <a> 替换为其文本 (img-only anchor → 空) 即 CF1 整体删除机制 (built 叛教尸.html L272-273 残留空 <p></p>);1,271 个肖像文件已在 _wiki_full_v2\images\ 本地存在 (manifest 3,403 项命中 1,271,7 个未命中系 alt 含 &#39; 转义的查询噪声),故 CF1 修复后肖像必然渲染,级联中唯一约束为 wiki_native.css img{max-width:100% !important} 与 #bodyContent img:not(.siteimg):not(.headimg){max-width:100%!important;height:auto} → 全正文列宽插入 statblock 第一行。isOurs=true:live wiki 该 class 由 site.styles (MediaWiki:Common.css) 约束,我方资产层未捕获该模块属构建/抓取层缺口,非 wiki 固有。fixableWithoutRescrape=true:在 _v2_compat.css 追加离线近似规则 (float:right + max-width 上限) 即可恢复可用版面,精确真值需 CF2 重抓但功能性修复不依赖网络。注意:本缺陷今日为潜伏态 (肖像被 CF1 删光),应与 CF1 修复绑定落地,且修复需顾及最宽 1500px 素材。

---

### [css/CF4-sitecss-semantic-classes] P3 — site.styles 层语义类零规则族: enlink (3.76%) / img-fullwidth (0.44%) / disambigpage (0.56%) — 原始样式随 Common.css 一起丢失且大多无法离线重建

**Evidence**

enlink: 928/24,666 (3.76%) ns0 页, 结构 <span class="enlink"><a class="external text" href="https://pathfinderwiki.com/...">英文名</a></span> 跟在中文术语后(例: 恶魔领主/黛丝娜/各神祇页), 零规则 → 渲染为全尺寸标准外链; 原生预期样式(推测小字号/弱化色)在未捕获的 Common.css 中, 样本页(战士)恰好不含 enlink(出现 0 次)故无法从 _native_sample_page.html 反推。img-fullwidth: 109 页(侏儒族裔/人偶族裔等)的 <img class="img-fullwidth"> 横幅图, 零规则 → 按自然尺寸而非通栏渲染, 意图明确可重建。disambigpage: 138 页消歧义框零规则。三者同根因(CF2), 与已立项 RC 项无重叠。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\wiki_native.css

**Fix spec**

可重建部分立即加入 _v2_compat.css §8: .mw-parser-output img.img-fullwidth { width: 100%; height: auto; }。enlink 建议保守最小化(不臆造): .mw-parser-output .enlink { font-size: .85em; opacity: .85; } 并标注待校正; disambigpage 暂不加规则。三者真值依赖 CF2 重抓 site.styles 后校正。

**Verifier note**: 复现成功，全部数字精确吻合。方法: (1) 临时脚本扫描 pf2wiki-scraper\out_v2\parsed\**\*.json (37,098 文件, ns0=24,666): enlink 928 页 (3.76%), img-fullwidth 109 页 (0.44%), disambigpage 138 页 (0.56%) — 与发现逐位一致。(2) grep _wiki_full_v2 下全部 *.css (_v2_compat.css / wiki_native.css / assets\native\) 对 .enlink/.img-fullwidth/.disambigpage 选择器: 0 条规则；整个 parsed 语料中也无任何这三类的 CSS 规则定义(仅 Manifest:Ihover.css 页面存在但不含)，即原始规则离线不可恢复。(3) 缺陷在构建产物中实际显现: pages\燎原党.html 含 <img class="img-fullwidth" data-file-width=2100 data-file-height=679>(横幅意图明确)、pages\矮人（消歧义）.html 含 <div class="disambigpage">、enlink 结构与声称的 <span class="enlink"><a class="external text" href="https://pathfinderwiki.com/...">英文名</a></span> 完全一致(样例: 阿波罗盖‧斯戎二世)。(4) isOurs 判定依据: assets\_native_sample_page.html 头部引用 load.php?modules=site.styles&only=styles，证明 live wiki 确有 site CSS 层而我方抓取/构建管线未捕获(CF2 根因)，非 wiki 固有；且样本页 0 次出现三类，证实无法从样本反推。(5) fixableWithoutRescrape=true 的限定: img-fullwidth 可离线确定性重建(width:100%)；enlink 可加保守最小化规则；disambigpage 建议暂不加规则——发现自提的修复方案均不需重抓即可落地，但 enlink/disambigpage 的精确原生样式真值仍需 CF2 重抓 site.styles 校正(属后续校准而非阻塞)。与 RC1-RC7 无重叠(disambig 框内 .flex 布局归 RC5，本项仅涉 .disambigpage 外层零规则本身)。

---

### [css/CF5-tailwind-arbitrary-value-family] P2 — Tailwind 任意值类 + 漏网静态工具类零规则族: my-[1em] (1.40%) / max-w-[350px] / text-[18px]+font-bold+my-0+border-black (地理页伪标题族) 等 — _v2_compat.css §8a 回填不全

**Evidence**

全语料 ns0 计数(实体解码后): my-[1em] 345 页(1.40%, <div class="intro my-[1em]" style="line-height:1.2em"> 简介块, 例 失窃的档案/生物（CRB）) → 上下 1em 外边距缺失, 简介与相邻块贴死; max-w-[350px] 75 页(0.30%, <div class="w-full max-w-[350px] float-right"> 地理页地图盒, 例 蛇龙诸王领地/奥斯布; 内层有 inline width:300px 故实际退化轻); text-[18px] 40 页 + font-bold 45 页 + my-0 40 页 + border-black 43 页(同族, 枪械工坊/黧水湾等地理页 <p class="text-[18px] font-bold"> 伪标题 → 渲染成普通正文字重字号); text-[#004416] 14 页(武器/状态等中枢页); gap-[10px] 5 页。已验证 built 页 class 属性为字面 [ ] (失窃的档案.html 含 class="intro my-[1em]"), 转义选择器可命中。同族先例: .w-1\/10 已于 _v2_compat.css:1342 回填。RC5 仅立项 .flex, 本族为其余缺口, 无重叠。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\失窃的档案.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\枪械工坊.html

**Fix spec**

在 _v2_compat.css §8a (L1333-1342 格式照抄)追加:
.mw-parser-output .my-\[1em\] { margin-top: 1em; margin-bottom: 1em; }
.mw-parser-output .my-0 { margin-top: 0; margin-bottom: 0; }
.mw-parser-output .font-bold { font-weight: 700; }
.mw-parser-output .text-\[18px\] { font-size: 18px; }
.mw-parser-output .text-\[24px\] { font-size: 24px; }
.mw-parser-output .max-w-\[350px\] { max-width: 350px; }
.mw-parser-output .max-h-\[500px\] { max-height: 500px; }
.mw-parser-output .border-black { border-color: #000; }
.mw-parser-output .gap-\[10px\] { gap: 10px; }
.mw-parser-output .text-\[\#004416\] { color: #004416; }

**Verifier note**: 复现成功，全部数字精确匹配。方法：临时脚本遍历 C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed 全部 37,098 个 JSON，取 ns==0 共 24,666 页，html.unescape 后以 token 边界正则计数：my-[1em] 345 页(1.40%)、max-w-[350px] 75(0.30%)、text-[18px] 40、font-bold 45、my-0 40、border-black 43、text-[#004416] 14、gap-[10px] 5、text-[24px] 5、max-h-[500px] 3 — 与发现声称值逐项一致，示例页(失窃的档案/生物（CRB）/蛇龙诸王领地/枪械工坊/黧水湾/武器/状态)也一致。built 页验证：pages\失窃的档案.html:263 含 class="intro my-[1em]"，pages\枪械工坊.html:289 含 <p class="text-[18px] font-bold"> 与 <hr class="my-0 border-black"/>，类名为字面 [ ]。零规则验证：grep assets\ 全部 12 个 CSS 文件，无任何上述类的选择器（仅 _fmt_navbox.css 注释提及 #004416，无关）；style.css L39-47 import 链含 _v2_compat.css；§8a (L1332-1342) 仅回填 flex-1/flex-col/items-center/justify-between/gap-1/my-2/ml-4/pl-2/w-full/w-1\/10，.w-1\/10 先例在 L1342，与 RC5(仅 .flex)无重叠。归属判定：live wiki 由 Tailwind 生成式样式表提供这些规则，镜像 §8a shim 明确以回填为职责但覆盖不全，属构建层缺口非 wiki 固有。修复无需重抓：Tailwind 任意值语义确定，提议的 10 条规则映射正确、转义选择器可命中字面类名，直接追加 _v2_compat.css §8a 即可。注意 gap-[10px]/text-[24px]/max-h-[500px] 命中页多为 测试首页/临时首页/首页备份 等非正文页，实际用户可见影响以 my-[1em](345 页简介块贴边)和 text-[18px]+font-bold+my-0+border-black(40 余地理页伪标题降级为正文)为主，P2 定级合理。

---

### [css/CF6-cite-references-columns] P3 — ext.cite 分栏类零规则: references-column-count(-2) / mw-references-columns — 长参考文献列表单栏渲染而非原生双栏

**Evidence**

全语料 ns0: references-column-count 96 页(0.39%), references-column-count-2 69 页, mw-references-columns 57 页(例: 奥苏姆港/瓦伦哈尔天路/不灭竞技场/传说之年)。12 个 assets/*.css 无任何选择器。根因: CF2 样本页偏置 — 战士页无 <references/> → ext.cite.styles 模块不在被抓 link 的模块清单中。MediaWiki 上游语义明确(column-count:2 / column-width:30em), 可无损重建; 退化表现为本应双栏的引用列表拉成单长栏。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css

**Fix spec**

在 _v2_compat.css §8 追加(MW 上游真值, 非臆造):
.mw-parser-output .references-column-count-2 { column-count: 2; }
.mw-parser-output .mw-references-columns { column-width: 30em; }
.mw-parser-output .references-column-count-2 li, .mw-parser-output .mw-references-columns li { break-inside: avoid; }

**Verifier note**: 复现成立,数字逐项吻合。方法:临时脚本扫 out_v2\parsed 全语料(37,098 json / 24,666 ns0):references-column-count 96 页(0.39%)、-2 共 69 页、mw-references-columns 57 页、并集 121 页;举例页(奥苏姆港/不灭竞技场/传说之年/凌乘)全部命中。grep 全站 *.css 无任何对应选择器(仅 topnav.css:185 有无关 column-count);style.css 仅 @import 9 个本地表,均不含 cite;构建页(pages\凌乘.html 等)原样携带类名且无 inline style 覆盖。根因复核:assets\_native_sample_page.html 无任何 cite_note/references,其 load.php 模块清单(ext.smw.*/site.styles/skins.dragonhide 等)确无 ext.cite.styles → CF2 样本页偏置成立。影响非纯理论:121 页中 86 页 ≥4 条引用、39 页 ≥15 条,最重 终焉之墙骑士 107 条 cite_note 被拉成单长栏;mw-references-wrap+mw-references-columns 是 Cite 扩展 responsive 模式服务端生成,live wiki 必伴随 ext.cite.styles(column-width:30em),故属构建/抓取层缺陷而非 wiki 固有。可不重抓修复:在 _wiki_full_v2\assets\_v2_compat.css 追加标准 MW 规则即可,但原修复设想有遗漏——语料另有 references-column-count-3 共 27 页(如 凌乘 28 条引用),须补 .references-column-count-3 { column-count: 3; } 并对 li 加 break-inside: avoid。

---

### [css/CF7-statblock-ritual-variant] P3 — .statblock-仪式 零规则 — 同族 statblock-专长/法术/动作 均有左侧色条 accent, 唯独仪式段缺失(32 页)

**Evidence**

_v2_compat.css 既有 .mw-parser-output .statblock-专长 { border-left: 4px solid #4a7d8f; } / .statblock-法术 { #8f4a7d } / .statblock-动作 { #d97706 } 及对应 body.dark 变体, 但语料中同模板产出的 statblock-仪式 (32 页: 创造半位面（2e）/呼唤灵魂/解锢术（2e） 等仪式条目)无任何规则 → 仪式 statblock 缺少兄弟段落都有的左侧色条, 同页面族内呈现不一致。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css

**Fix spec**

紧邻既有 statblock- 规则处追加(格式照抄):
.mw-parser-output .statblock-仪式 { border-left: 4px solid #7d8f4a; }
body.dark .mw-parser-output .statblock-仪式 { border-left-color: #a3b66f; }

**Verifier note**: 复现成立。(1) 数字核实: rg 'statblock-仪式' 在语料 pf2wiki-scraper\out_v2\parsed 命中恰 32 个 JSON, 且构建产物 _wiki_full_v2\pages\ 中也恰 32 个 html 含该类(类名原样进入产物); 抽样 4 页(隐形仆役群/问道自然/邪魔契约/通晓传奇, 均 ns0 仪式条目)class 形如 "quote-block statblock statblock-仪式", parse.text 内无内联 <style> 自带样式。(2) 规则缺失核实: _v2_compat.css L1366-1368 仅有 .statblock-专长(#4a7d8f)/.statblock-法术(#8f4a7d)/.statblock-动作(#d97706), L1451-1453 为对应 body.dark 变体, 全部 assets CSS(style.css/pf2_theme.css/_components.css/_fmt_mobile.css)中均无任何 statblock-仪式 规则。(3) isOurs: 该色条是我们 compat 层自创装饰(8d 段注释"按类型给左边一条色带：专长=青灰/法术=紫红/动作=琥珀", 其余 CSS 与原生采样页均无此类变体规则), 基础 .statblock 仅 1px 边框无色带 → 同族四类中三类有 4px 左色条唯 仪式 没有, 此族内不一致系构建层引入而非 wiki 固有。覆盖面: 专长 1609 页/法术 618/动作 306/仪式 32(构建页计数)。(4) 修复: 不需重抓, 在 _v2_compat.css L1368 后与 L1453 后各加一行(建议色 #7d8f4a / dark #a3b66f, 与提案一致)即可。附注: 原生采样页 assets\_native_sample_page.html L383 存在空后缀变体 class="statblock statblock-"(模板对无类型块输出空后缀), 不影响本结论。

---

### [js/INT-1] P0 — mw_collapsible.js 折叠 TABLE 时隐藏整个 tbody(含标题行与 toggle 本身)——1,648 页导航框/折叠表在首屏完全消失且不可恢复,另 7,206 页点击即消失

**Evidence**

代码根因: assets/mw_collapsible.js findContent() 第17-23行对 TABLE 返回 `el.querySelector('tbody')`,toggle()/初始折叠路径(第43-45、83-94行)判定 content!==el 后执行 `content.style.display='none'`,把含 navbox-title 和 [展开] 按钮的整个 tbody 一起隐藏;第47-53行『隐藏首行以外各行』的正确分支因 tbody 恒存在而成死代码。第102-107行 autocollapse>=2 规则在 init 时给全部 .mw-autocollapse 加 mw-collapsed,直接走该坏路径。浏览器实测(localhost 静态服务): pages/战士.html 两个 navbox 载入即 height=0、innerText 为空、toggle 不可见;pages/萨克里斯诸神.html 7 个源码自带 mw-collapsed 的神祇 navbox(主流信仰/种族神/至高天领主等)全部 height=0 内容不可达;pages/苏剌嘎.html 点击 [折叠] 后 tbody display:none、toggle offsetParent=null、recoverable=false。全语料精确计数(37,098 个 parsed JSON 全扫): 含 mw-collapsible 表格的页面 7,206;autocollapse>=2 首屏即消失 896 页 ∪ 源码 mw-collapsed 表格首屏消失 800 页 = 1,648 页(重叠48,ns0 占 1,647)。对照健壮性问题: mw-collapsed 初始态仅对『div+显式 .mw-collapsible-content』正确(实测 pages/可选规则.html 7 个 div 折叠/展开往返正常)。脚本注入确认: build_v2.py 第677行对每个构建页注入 <script defer src="../assets/mw_collapsible.js">,萨克里斯诸神.html 实测含该标签。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\mw_collapsible.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\战士.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\萨克里斯诸神.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\苏剌嘎.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py

**Fix spec**

改 assets/mw_collapsible.js(纯前端,无需重建页面): (1) findContent() 对 TABLE 不再返回 tbody,改返回 null 走行级处理;(2) 折叠/初始折叠时对 TABLE 仅隐藏『toggle 所在行(无 caption 时即首行)之外』的 tbody>tr,caption 与标题行永远可见——即复刻 MediaWiki jquery.makeCollapsible 行为;(3) 展开时恢复这些行 display=''。验收: 战士.html 首屏两 navbox 显示标题行+[展开];萨克里斯诸神.html 7 个折叠 navbox 标题可见可点开;苏剌嘎.html 点 [折叠] 后标题行仍在、再点 [展开] 完整恢复。

**Verifier note**: 独立复现成功,全部证据成立,判定 P0 属实。(1) 代码核查: 亲读 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\mw_collapsible.js — findContent() 第21行对 TABLE 返回 el.querySelector('tbody');toggle()(第43-45行)与初始折叠(第84-87行)均因 content(tbody)!==el 而执行 content.style.display='none',把含 navbox-title 与 toggle 的整个 tbody 隐藏;第47-53/88-93行的行级正确分支因 DOM 中 tbody 恒存在(语料 HTML 还显式带 <tbody>)而为死代码;第102-107行 init 时 .mw-collapsible.mw-autocollapse>=2 即全部加 mw-collapsed 走坏路径。实测语料类名确为 mw-autocollapse(非 MediaWiki 常见的裸 autocollapse),故该路径真实触发。navbox-inner 表无 caption/无 thead/无 .mw-collapsible-content(战士.html 中 grep 计数为 0),toggle 被 append 进 tbody 首行 th 内,随 tbody 一起消失。build_v2.py 第677行确认每页注入 <script defer src="../assets/mw_collapsible.js">。(2) 全语料计数复现(临时脚本扫 pf2wiki-scraper\out_v2\parsed 全部 37,098 个 JSON 的 parse.text): 含 mw-collapsible TABLE 页面=7,206;autocollapse>=2 且含 autocollapse 表=896;源码 mw-collapsed 表=800;并集 1,648,重叠 48,ns 分布 {0:1647, 4:1} — 与待核查数字逐项吻合(原发现 ns0=1,647 亦对)。(3) 浏览器实测(python http.server 8741 + Playwright): pages/战士.html 两个 mw-autocollapse navbox 载入即被加 mw-collapsed,rect.height=0、tbody display:none、innerText 空、toggle offsetParent=null;pages/萨克里斯诸神.html 8 个折叠表中 7 个源码 mw-collapsed 全部 h=0、toggle 不可见、内容不可达;pages/苏剌嘎.html 展开态 navbox h=422.7px,点击 [折叠] 后 h=0、tbody none、toggle 不可见(userRecoverable=false;程序化二次 click 可恢复至 422.7px,证明仅 UI 入口丢失)。isOurs=true: mw_collapsible.js 是构建层自写的 jquery.makeCollapsible 替代品(文件头注释自述),wiki 原生模块对表格只隐藏首行以外各行,故为我方引入缺陷而非 wiki 固有。fixableWithoutRescrape=true: 纯前端修 assets\mw_collapsible.js 单文件即可(对 TABLE 改为行级隐藏、保留标题行/caption),无需重抓也无需重建 3.7 万页;唯一小坑是 build_v2.py 注入的 script 标签无 ?v= 缓存戳(文件头注释声称有 ?v=v2e 但第677行实际没有),离线用户可能需强刷。修复设想方向正确,验收标准可按原文执行。

---

### [js/INT-2] P2 — wikitable_sort.js 给全部 wikitable 强加排序但无分组/跨列防护——含组小标题行(th-only)的 22 页表格排序后分组被打散、小标题沉底

**Evidence**

wikitable_sort.js init() 第181行选择器 `.mw-parser-output table.wikitable` 无差别装饰(语料中 class=sortable 仅出现在 10 个 Data:*.tabx 数据页,正文 0 页——即原维基正文表格根本不可排序,排序是离线版自加功能);decorate() 把首行外所有 tr 当数据行排序,th-only 组小标题行被一并排序,且 sortBy 用 `tr.children[colIdx]` 取列、对 colspan/rowspan 零处理。浏览器实测 pages/宝石与艺术品.html: 56 行表内 5 个组小标题(中等半宝石/高等半宝石/次等宝石/中等宝石等,原位置 15/30/41/46)点首列排序后沉到 51-54 行,sp/gp 不同组数据交错,呈现语义被破坏(第三次点击可恢复原序,实测 restoredOk=true)。全语料精确计数: 含 mid-table th-only 行的 wikitable 页 22 页(机械师/御能师/冒险之路/道具(2e)/秘示域(2e)等);含 colspan>=2 单元格的 wikitable 估 59 表/29 页(5000 抽样)。健壮性顺检结论(rowspan): 全语料 wikitable 中 rowspan>=2 为 0 例——rowspan 仅出现于 navbox 表(5000 抽样 64 处),navbox 非 wikitable 不会被排序,故 rowspan 风险目前是潜在而非现实,但排序器确无任何 rowspan 守卫,一旦语料更新引入即损坏。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\wikitable_sort.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\宝石与艺术品.html

**Fix spec**

改 wikitable_sort.js decorate 前置守卫: 扫描 bodyRows,若存在 (a) th-only 行(组小标题)、(b) 任一单元格 rowspan>=2、(c) 任一数据行单元格数与表头列数不一致(colspan 错位),则跳过该表不装饰(不加 sortable class 和 ↕ 指示器)。可选增强: 对 (a) 类表改为按组分段排序(以 th-only 行为界,各段内排序、段保持原位)。验收: 宝石与艺术品.html 首表表头不再出现 ↕;无小标题的普通列表表(如生物列表)排序功能保持不变。

**Verifier note**: CONFIRMED — independently reproduced all core claims; two stat deviations found, both making the defect WORSE than reported. Method: (1) read C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\wikitable_sort.js — line 181 selector `.mw-parser-output table.wikitable` decorates indiscriminately; findHeader() returns ALL rows after header as bodyRows (no th-only filter); sortBy() uses `tr.children[colIdx]` with zero colspan/rowspan handling — code claims exact. (2) Full-corpus scan (own HTMLParser script over all 37,098 parsed JSON, 0 parse errors): class="sortable" appears on exactly 10 pages, all ns=3500 Data:*.tabx/.tab, 0 main-ns — sorting is a build-layer-added feature, NOT wiki behavior, so "faithful mirror" defense does not apply (isOurs=true; script injected at line 18 of built pages by build_v2.py template). Pages with mid-table th-only rows in wikitables = exactly 22, all named examples present (宝石与艺术品 has 5+4 across 2 tables; 御能师 6; 冒险之路 3). (3) Live browser repro (Playwright via localhost:8642): 宝石与艺术品.html table 0 (56 rows) is decorated; group-subtitle th-rows sit at idx 15/30/41/46/51 pre-sort; one click on d% column sinks all 5 to rows 51-55 and interleaves cross-group data (玛瑙 1-7 from 次等半宝石 adjacent to 钻石（大）1-25 from 高等宝石 — sp/gp price scales mixed); 3rd click restores original order (restoredOk=true). DEVIATIONS: (a) colspan>=2 full-corpus is 100 wikitables on 91 pages (claim's 5000-file sample said ~59/29 — undercount, direction holds); (b) claim "rowspan>=2 in wikitables = 0 full-corpus" is WRONG: exactly 1 exists — 化形生物变体 (parsed\0d\e60e753ec644b4b81dc31719f056b558971058.json, Werebear/Wererat/Weretiger rows with rowspan=2). Live test on 化形生物变体.html: table IS decorated, one sort click detaches the three 3-cell 爪抓 continuation rows from their rowspan parents and clusters them after 熊化人 — rowspan breakage is ACTUAL today, not merely potential, so the proposed guard (b) protects a real page. Fix is pure client-side JS (pre-decorate guard: skip tables with th-only body rows / rowspan>=2 / column-count mismatch), no corpus data involved — fixableWithoutRescrape=true. P2 severity reasonable: 22 pages user-visibly broken on interaction, recoverable via 3rd click, no data loss.

---

### [js/INT-4] P2 — mw-customtoggle 无处理器 + 无 content 包裹的 div.mw-collapsible 折叠完全失效——8 页(含核心枢纽页 规则索引)横幅点击无反应、[展开/折叠] 只翻标签不动内容、24 个 mw-collapsed 区块全部以展开态渲染

**Evidence**

语料全扫: mw-customtoggle 8 页(规则索引/火花典卫/断空/精金回响/塞尔德格·贝德利斯等),与『collapsible div 数 > mw-collapsible-content 数』的 8 页完全同集。结构: `<div class="mw-customtoggle-PZO12001">` 内含书名横幅 div + `<div class="mw-collapsible mw-collapsed" id="mw-customcollapsible-PZO12001">`(无 .mw-collapsible-content 子层)。浏览器实测 pages/规则索引.html: 25 个横幅/25 个 collapsible/24 个 mw-collapsed;点击《玩家核心》横幅 display 前后均 block(changed:false)——grep 全部 assets/*.js 无 mw-customtoggle 字样,处理器缺失;注入的 [折叠] toggle 点击后 display 仍 block——mw_collapsible.js findContent() 对无 content 包裹的 DIV 返回 el 自身,toggle() 中 content===el 落入 `el.tagName==='TABLE'` 分支外什么都不做,初始 mw-collapsed 同理被忽略(故 24 个本应折叠的区块全展开,页面变成一根超长直列;内容可读,无数据丢失)。另: 同为内联交互件的 cf-filter(351 页,语料内联 <script> 全部为该件)经实测在离线版完整可用(萨克里斯诸神.html 点『变化』筛选 6→1),build 未剥内联脚本,无需处理;tabber/NavFrame/jquery-tablesorter 语料 0 页,无缺口。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\mw_collapsible.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\规则索引.html; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed\37\5c6795300d7199835d17e5704cbfa7bde8ae2b.json

**Fix spec**

改 mw_collapsible.js 两点: (1) injectToggle 中当元素非 TABLE 且无 .mw-collapsible-content 时,把 toggle 以外的全部子节点包进新建的 div.mw-collapsible-content——content-less div 的折叠与 mw-collapsed 初始态随之自然修复;(2) init 末尾增加委托处理器: 对 class 匹配 /mw-customtoggle-(\S+)/ 的元素绑定 click(点击目标在 <a> 内时放行),切换 document.getElementById('mw-customcollapsible-'+id) 的折叠态(复用 toggle 逻辑,支持一个 id 对应多个 collapsible)。验收: 规则索引.html 首屏 24 个书目区块呈折叠态只显书名横幅,点横幅或 [展开] 可开合往返。

**Verifier note**: 独立复现成功，发现属实。(1) 语料复现: 全扫 37,097 个 parsed JSON，含 mw-customtoggle 的恰为 8 页(规则索引 25 个/塞尔德格·贝德利斯 2 个/精金回响、火花典卫、氏族联合、断空、恶魔之结、卡茂格日志各 1 个)；按精确 class-token 计数(注意: 朴素正则 \bmw-collapsible\b 会误匹配 mw-collapsible-content 而虚报 117 页，必须按 token 精确匹配)，『div.mw-collapsible 数 > .mw-collapsible-content 数』的页面集合与该 8 页完全相等(8 页 content 均为 0)，集合相等性=True。(2) 处理器缺失复现: grep customtoggle 扫 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\ 全部 13 个 *.js = 0 命中。代码审读 assets\mw_collapsible.js: 第 22 行 findContent 对无 content 包裹的非 TABLE 元素返回 el 自身；toggle()(44-54 行)与初始折叠块(84-94 行)在 content===el 时仅处理 TABLE 分支，DIV 落空为 no-op——与报告描述逐行吻合。(3) 浏览器实测复现(Playwright + 本地 http.server, pages\规则索引.html): 25 横幅/25 collapsible/25 个带 mw-collapsed class(报告称 24 系其先点过一次 toggle 翻掉了 class，静态计数实为 25，量级无碍)，但视觉隐藏数=0，全部展开，页面高 15,236px；点击《玩家核心》横幅前后 display:block/offsetHeight 1770px 完全不变(changed:false)；点注入 toggle 后标签 [展开]→[折叠]、mw-collapsed class 25→24 被翻掉，但 display/高度仍 1770px 不变——三项异常行为全部复现。(4) 归属: 语料 parse.text(维基官方渲染 HTML)本就如此(无 content 包裹是 MediaWiki 原生输出，由 live wiki 的 jquery.makeCollapsible 运行时模块负责包裹与 customtoggle 绑定)；缺陷在于我们用自写 mw_collapsible.js 替代该模块却未覆盖这两个能力，属构建层(离线运行时)引入，isOurs=true。(5) 可修性: 纯 JS 修改 assets\mw_collapsible.js 即可(包裹 content + 委托绑定 customtoggle)，内容全部已在本地 HTML 中无数据丢失，无需重抓，fixableWithoutRescrape=true。报告中的旁证(cf-filter 内联脚本可用、tabber/NavFrame 0 页)未逐一复核，不影响主结论。涉及文件: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\mw_collapsible.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\规则索引.html(269-271 行为典型结构: banner div.mw-customtoggle-PZO12001 内含书名条 + 无 content 包裹的 div.mw-collapsible.mw-collapsed#mw-customcollapsible-PZO12001); 语料样本 C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\parsed\37\5c6795300d7199835d17e5704cbfa7bde8ae2b.json。P2 定级合理: 无数据丢失、内容可读，但核心枢纽页交互完全失效。

---

### [search/SRCH-1] P0 — 重定向别名完全未入搜索索引 — AC/巨龙/挥砍/先攻/豁免/HP 等 3,614 个别名查询返回零相关结果

**Evidence**

metadata.json redirect_map 共 5,799 条,其中 3,614 个源标题不在 titles.js 的 37,097 条目中(2,185 个恰好同名实页除外)。实测(复刻 search.js 算法):查询 'AC'(redirect_map: AC→护甲)→ 4,701 候选中 '护甲' 排名 None(根本不是候选,#1 是 ns102 桩 '属性:AC');查询 '巨龙'(→龙)→ 290 候选中 '龙' rank=None;查询 '挥砍'(→伤害类型)→ 1,094 候选中 '伤害类型' rank=None。常用玩家术语 HP/DA/先攻→遭遇模式/豁免→检定 同样全部失效。build_v2.py 虽为这些别名生成了 meta-refresh 跳转页,但 build_search_v2.py 的 iter_parsed 只读 parsed/*.json,从不读 redirect_map。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js

**Fix spec**

build_search_v2.py: 在 build() 中加载 META_FILE 的 redirect_map;对每个 (alias→target) 且 target 在已索引标题集合中、alias 不在标题集合中的条目,追加合成条目 {i:next_id, t:alias, h:page_href(目标ns,target), k:'p', e:'重定向 → '+target},并把 alias 本身按 tokenize_latin/cjk_bigrams 写入倒排;类型码复用目标页的码。search.js 可选增强:结果行检测 e 以 '重定向 → ' 开头时渲染 'AC → 护甲' 样式。无需重爬。

**Verifier note**: 复现成功,所有数字精确吻合。方法:(1) 直读 metadata.json — redirect_map 恰为 5,799 条;(2) 解析 index/titles.js — 恰为 37,097 条目;集合差:3,614 个重定向源标题不在索引(2,185 个为同名实页),与声称完全一致;细化:3,614 中 3,569 个目标非空、3,564 个目标本身已被索引(可干净修复),45 个目标为空串;(3) 把 search.js 算法完整移植为 Python 临时脚本(md5 首字节分桶、posting-list 交集、标题子串并集、score+popularity 排序),实测:'AC'→护甲 4,701 候选 rank=None 且 #1=属性:AC(与声称逐字吻合);'巨龙'→龙 290 候选 rank=None;'挥砍'→伤害类型 1,094 候选 rank=None;先攻/豁免/HP/DA 全部 rank=None;(4) 因果链确认:build_search_v2.py 第 33 行定义 META_FILE 但全文从未读取,build() 仅消费 iter_parsed(parsed/*.json);而 build_v2.py 第 853/1040 行确实加载 redirect_map 并生成跳转桩(实查 pages\AC.html 存在,380 字节,meta-refresh→category/护甲.html),证明别名数据本地齐备、纯属搜索构建层遗漏。归属判定:MediaWiki 原生搜索会匹配重定向标题,故这是镜像保真缺陷而非 wiki 固有。可离线修复:redirect_map 在本地 metadata.json,合成条目方案无需网络。修复注意:① 实际可修约 3,564 条(45 空目标+5 目标未索引须跳过);② 别名 href 应复用 build_v2.py 的 _resolve_redirect_target 链式解析(或直接指向已存在的别名跳转桩)而非朴素 page_href(target),以兼容 A→B→C 多跳及 RC1 分类劫持后的真实落点。涉及文件:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py(缺陷点)、C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json(数据源)、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index\titles.js(索引产物)、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js(查询端,候选集仅来自倒排+标题子串,别名缺席即不可达)。

---

### [search/SRCH-2] P1 — ns3500 Data:*.json 页严重污染英文查询 — 'AC' top50 中 46 条、'dragon' 49/50 条是数据页,且 11,867 个数据页全部归入'其他/短条目'类型

**Evidence**

实测:查询 'AC' top50 有 46 条 k='d' 数据页(Data:Items-Sack.json、Data:Traits-Acid.json 等);'dragon' 49/50;'sword' top10 有 10 条数据页,#1=Data:Creatures-Swordfish.json;'Fireball' #1/#2 是 Data:Spells-Fireball.json(175分)/Data:Items-Wand of Smoldering Fireballs.json(156分),正主 '火球术' 仅 2 分排 #3。原因:search.js 第 484-486 行 k==='p' 仅 +5 分,而数据页标题含英文名可拿 +200 子串分。另 11,867 个 k='d' 条目 type 全为 other/stub(数据页无 categories);search.js resolveType 第 386-397 行的 Data 页 slug 回退是死代码:item.h='data/Spells-Fireball.json.html',decoded.split('-',1)[0]='data/Spells' 永不等于 'Spells',且 types.js codes 覆盖全部 37,097 条致回退永不执行。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py

**Fix spec**

search.js query() 评分处(第 479-486 行):对 it.k==='d' 在标题命中档施加大额罚分(如 score -= 250),保证任何 'p' 页的同档命中恒在数据页之上;或在 ranked.sort 中把 k==='d' 作为末级分组。build_search_v2.py infer_type():对 ns==3500 按标题前缀映射类型(Data:Spells-→S, Data:Feats-→F, Data:Creatures-→C, Data:Items-→I, Data:Traits-→R, Data:Conditions-→N),使类型筛选条能区分数据页;同时删除 search.js 中失效的 slug 回退或改为 decoded.split('/').pop().split('-',1)[0]。

**Verifier note**: 复现方法:写 $env:TEMP\srch2_repro.py 完整模拟 search.js query() 评分链(parseQuery→词/二元组分片求交→titleSubstringSearch 并集→第474-498行评分排序,含 pop 次级排序),数据源为 index\titles.js(37,097条,含pop)、index\types.js、index\shards\w_*.js/b_*.js。逐项核验:[1] 'AC' top50 中 k='d' = 46/50(精确吻合;细节修正:前4名实为 p 页"属性:AC"200分/"属性:AC加值"198分,污染始于第5位);[2] 'dragon' 49/50 吻合;[3] 'sword' top10 = 10/10 数据页,#1=Data:Creatures-Swordfish.json(171分)吻合;[4] 'Fireball' #1=Data:Spells-Fireball.json(175)、#2=Data:Items-Wand of Smoldering Fireballs.json(156)、火球术 2 分排 #3,全部精确吻合;对照 '火球术' 中文查询 0 数据页污染,确认仅英文查询受害。[5] k='d' 条目恰 11,867,type 全为 other(11,574)+stub(293),吻合。[6] 评分代码亲读确认:search.js 第480行子串+200、第484行 k==='p' 仅+5。[7] slug 回退双重死代码确认:types.js codes 长度 37,097==items 且全部14个码字符均在 legend 内(resolveType 第378-383行快路径恒返回);即便执行,实测 h='data/Spells-Fireball.json.html' decode 后 split('-',1)[0]='data/Spells' 永不等于 'Spells'。[8] 归因:build_search_v2.py infer_type()(第98-111行)仅看 parse.categories,而 ground-truth 抽样 400 个 ns3500 JSON 的 categories 全为空 → 必然落 O/U;此为我们自建搜索层(build_search_v2.py+search.js)的缺陷,live wiki 的 MediaWiki 搜索无此排序,非镜像固有。[9] 可修性:数据页标题前缀分布 Feats 4821/Items 3165/Creatures 1381/Spells 1220/Traits 573/Backgrounds 460/Vehicles 96/Companions 91/Conditions 42/杂项 18,提议的前缀映射(加上 Backgrounds→B)可覆盖 99%+;评分罚分纯 search.js 改动。两项均只需本地语料重建索引,无需重抓。涉及文件:C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py、C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index\{titles,types}.js。修复设想注意点:293 个数据页因 body<120 被标 U(stub),前缀映射若想全量生效需在 stub 判定前对 ns3500 分支处理。

---

### [search/SRCH-3] P1 — '规则导航' 导航模板吞噬 body[:600] 索引窗口和摘要 — 核心规则页(伤害类型/遭遇模式/护甲等 87 页)的正文词条未被索引

**Evidence**

87 个页面的 excerpt 前 30 字符含 '规则导航'(97 页任意位置),全是高价值规则中枢:伤害类型、遭遇模式、生命值、治疗与濒死、宝藏、载具、运行游戏等。'伤害类型' 的 excerpt[:90]='规则导航 本导航用于规则相关内容…《玩家核心》 1、引言 Introduction 序言…' 纯属模板目录;build_search_v2.py 第 334 行只索引 body[:600],导航文本占满窗口,导致 '挥砍' 查不到 '伤害类型'(1,094 候选中 rank=None)、'AC' 查不到 '护甲'(其 excerpt 同样以导航列表开头)。这与 SRCH-1 叠加使规则概念双重不可达。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py

**Fix spec**

build_search_v2.py iter_parsed() 第 239 行附近:在现有 .well.quote-success/.quote-primary 剔除之后,同步 decompose 规则导航模板容器(检查语料 HTML 实际选择器,通常为 .navbox / table.navbox / 含'规则导航'文本的 .mw-collapsible 顶层框)再 get_text;这样 body[:600] 与 excerpt 都落在真实正文上。重建索引后验证:'挥砍' 应召回 '伤害类型','伤害类型' excerpt 应以正文开头。

**Verifier note**: 复现成功，全部数字精确吻合。方法与数据：(1) 解析 index\titles.js (37,097 items)：excerpt[:30] 含'规则导航'=87 页、任意位置=97 页，与发现完全一致；样本全是规则中枢(载具/遭遇模式/宝藏/生命值、治疗与濒死/运行游戏/伤害类型/护甲等)。'伤害类型'(id=10286) excerpt 确为纯导航目录文本。(2) 检索失败实锤：按 build_search_v2.py 同款 md5 分桶解析 shards\b_7f.js(挥砍桶)：bigram '挥砍' posting list 恰为 1,094 个候选，不含 id 10286；而标题派生 bigram '类型' 含之 → '挥砍'查不到'伤害类型'仅因正文窗口被吞。w_a.js：word 'ac' 3,708 候选，不含 27270(护甲)，'AC'→护甲同样失败。(3) 根因复现：parsed\46\8e00c67845754a0e00549fd63efea97dcb2fa6.json('伤害类型')按 build_search_v2.py 第231-244行同流程剥离后 body len=4,550，body[:600] 100% 是导航文本；真实正文'物理伤害'首现 offset 2288、'挥砍' offset 2379(出现2次)，远超第334行的 600 字符索引窗口；导航文本总长 2,272 字符。(4) 归属：导航模板是 wiki 原生内容，但 body[:600] 截窗+不剥离导航是 build_search_v2.py(C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py 第334行索引、第246行 excerpt)自有设计，live MediaWiki 全文检索无此约束 → 构建层缺陷。(5) 可修性：语料完整在本地，仅需改 iter_parsed() 并重建 index\ 。修复选择器更正：'规则导航'框的实际容器是 .mw-parser-output 顶层 <div class="hidden-sm hidden-xs">(6 个抽样页面均为此结构、textlen 恒为 2272)，不是发现里猜的 .navbox/.mw-collapsible(table.navbox 是页底另一个'GM帷幕'速查框，仅557字符不占窗口)。注意勿盲目 decompose 所有 div.hidden-sm.hidden-xs(响应式类可能包裹他页正文)，建议仅剔除文本以'规则导航'开头的该类顶层 div；剥离后'挥砍'落于正文 ~offset 107，重建后即可召回。

---

### [search/SRCH-4] P2 — 英文原名无权重 — 'Fireball' 时正主 '火球术' 仅得 2 分,排在垃圾数据桩之后

**Evidence**

'火球术' excerpt 即 '火球术 Fireball 法术 3 …','治疗药水' 为 '治疗药水 Healing Potion 物品1+ …' — 英文官方名稳定出现在正文头部并已进倒排(故能召回),但评分上只算内容命中(0 分档),最终 score=2(5-3 长度罚)。实测 'Fireball' → 火球术 score 2 排 #3,低于 Data:Spells-Fireball.json(175)和 Wand of Smoldering Fireballs(156)。所有'英文名查中文条目'场景同此模式。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_search_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js

**Fix spec**

首选 build 侧:iter_parsed 时从 body 头部提取英文名(标题之后的首段连续 Latin 词串,如 body 去掉标题前缀后匹配 ^[A-Za-z][A-Za-z '\-]+),作为新字段 n 写入 titles.js 条目;search.js 评分时对 (it.n||'').toLowerCase() 与查询做 ===/startsWith 比对,命中按 +900/+450 计(略低于中文标题档)。最小替代方案(纯 search.js):内容命中且 excerpt 前 40 字符内含完整查询词时 +300。配合 SRCH-2 的数据页罚分,'Fireball' 即可 #1 命中火球术。

**Verifier note**: 复现成功,数字逐项吻合。方法:写 $env:TEMP\srch4_repro.py,加载真实索引 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index\titles.js(37,097 条目)+ shards\w_f.js,逐行模拟 search.js(C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js L474-489)评分排序。实测 'fireball' 倒排 posting=4 ids+标题子串并集=5 候选,排名: #1 Data:Spells-Fireball.json score=175 (200子串-25长度), #2 Data:Items-Wand of Smoldering Fireballs.json score=156, #3 火球术 score=2 (0+5ns-3长度,pop=113) — 与发现声称的 175/156/2、排 #3 完全一致。'Healing Potion' 同模式:治疗药水 score=1 排 #3,落后 Data:Items-Healing Potion.json(170) 和 药水(3)。代码核对:search.js 评分只有 title ===/startsWith/indexOf 三档(+1000/+500/+200),无任何英文名字段;build_search_v2.py 的 titles.js 条目仅 {i,t,h,k,e},英文名只进倒排(召回)不进评分。isOurs=true:搜索/排序完全是我们离线构建层(build_search_v2.py+search.js)自造,live wiki 用 MediaWiki 服务端搜索,此缺陷非镜像固有。fixableWithoutRescrape=true:英文官方名已在本地语料 body 头部 — 实测 13,936 个 k='p' 页 excerpt 以自身标题开头,其中 12,871 个(92.4%)标题后紧跟可提取的 Latin 词串(如 至古圣天龙→Empyreal Archdragon),build 侧提取 n 字段或纯 search.js 的 excerpt 头部加分方案均只依赖本地数据,无需重抓。

---

### [search/SRCH-5] P2 — Latin 标题子串匹配无词边界 — 'AC' 以 +200 分命中 Sack/Tack/Acid/Reach/Cackle/Vaccine 等无关标题刷满首屏

**Evidence**

search.js titleSubstringSearch(第 513-524 行)与评分(第 480 行 tl.indexOf(lower)>=0 → +200)均用裸 indexOf。实测 'AC' top12:#5-#12 为 Data:Items-Sack.json(180)/Items-Tack.json(180)/Traits-Acid.json(179)/Traits-Reach.json(178)/Traits-Brace.json(178)/Feats-Cackle.json(178)/Spells-Redact.json(177)/Items-Vaccine.json(177),全部是英文单词内部子串误命中;MediaWiki 原生搜索按词匹配不会出现这些结果。CJK 子串不受影响(中文按字粒度子串合理)。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js

**Fix spec**

search.js:对纯 ASCII 查询(/^[\x20-\x7e]+$/)改用词边界匹配 — 构造 new RegExp('(^|[^a-z0-9])'+escapeRegex(lower)) 测试 tl,titleSubstringSearch 与 +200 评分分支共用同一谓词;CJK 或混合查询维持 indexOf 现状。修复后 'AC' 的 +200 档应只剩标题确含独立 AC 词的页面。

**Verifier note**: CONFIRMED. (1) Code: search.js line 480 `tl.indexOf(lower)>=0 → +200` and titleSubstringSearch lines 513-524 both use bare indexOf, no word boundary for Latin queries. (2) Reproduced ranking exactly: re-implemented query() in Python against real index (index/titles.js 37,097 items + index/shards/w_a.js 1,379 keys); query 'AC' top12 = 属性:AC(200), 属性:AC加值(198), Owb Pact(197), Indomitable Act(190), then #5-#12 Items-Sack(180)/Items-Tack(180)/Traits-Acid(179)/Traits-Reach(178)/Traits-Brace(178)/Feats-Cackle(178)/Spells-Redact(177)/Items-Vaccine(177) — identical to claim; 8/12 first-screen results are word-internal false matches. (3) Path pinned: all 8 are ABSENT from inverted-index posting list SH['ac'] (3,708 ids) — they enter only via titleSubstringSearch union (line 464) and are boosted only by line 480. Magnitude: 1,044 titles contain substring 'ac', only 72 pass word-boundary test (^|[^a-z0-9]) — 972 (93%) false. (4) isOurs: search.js is our hand-written client search (src-tauri copies are build derivatives); MediaWiki native word-based search would never return Sack/Tack for 'AC'. (5) Fix is a local JS edit using existing titles data — proposed ASCII-only word-boundary predicate verified to cut hits 1,044→72; no rescrape or index rebuild needed. Files: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js (fix here; bundle copies regenerate on build); repro scripts $env:TEMP\srch5_repro.py, $env:TEMP\srch5_path.py.

---

### [search/SRCH-6] P2 — 英文前缀匹配仅在'精确词缺失'时触发 — 'fire' 因自身是索引词而完全屏蔽 fireball/firebrand 扩展,与 search.html 宣传的前缀搜索矛盾

**Evidence**

search.js 第 429-447 行:if (sh && sh[w]) 直接用精确 posting,else 才做 prefix scan。实测 w_f 分片中 'fire' 为精确词(142 postings),致查询 'fire' 的 171 个候选不含任何 fireball 页 — '火球术' 在 top200 之外;而 'firebal'(非索引词)反而能扩展到 fireball(4 postings)。search.html 第 348 行提示文案承诺『英文支持前缀(如 demo → demon, demonstrate …)』,实际仅对碰巧不成词的前缀成立。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.html

**Fix spec**

search.js query():把精确命中与前缀扫描改为始终合并 — 对每个 latin 词收集 exact = sh[w]||[],再遍历桶内 key.startsWith(w) 的词合并去重(设上限如 5,000 id 或 200 个扩展词防爆),排序后 push;精确命中词的 posting 排前可另加小额评分(在 ranked 阶段给标题含完整词者已有 +200,足够)。修复后 'fire' 应能召回火球术(其正文含 Fireball)。

**Verifier note**: REPRODUCED EXACTLY, and slightly worse than reported. Method: temp scripts parsed index\shards\w_f.js / w_d.js (JSONP) and index\titles.js (37,097 items), replicating search.js query() lines 427-468 verbatim. (1) Code confirmed: line 430 `if (sh && sh[w])` pushes exact postings and the prefix scan only runs in the else-branch. (2) 'fire' is an exact index word with exactly 142 postings; simulated query('fire') = exactly 171 candidates (postings ∪ title-substring). (3) sh['fireball'] = 4 postings: ids 4228 火球术, 9259 焰龙兽, 12777 火球符文, 29093 Data:Spells-Fireball.json. 火球术 is ENTIRELY ABSENT from the 171 candidates (stronger than the claimed 'outside top200' — unrecoverable at any limit); only Data:Spells-Fireball.json appears (rank #8) via the title-substring union, i.e. users get the raw data page but never the main article. (4) 'firebal' (non-indexed) prefix-expands to 6 candidates including 火球术 — confirming the paradox. (5) NEW: the hint's own advertised example is broken — 'demo' is itself an exact index word (1 posting) in w_d.js, so 'demo' never expands to 'demon' (32 postings)/demonstrate; search.html line 348 contradicts actual behavior with its own example. isOurs=true: search.js/search.html/index are pure build-layer additions (live wiki uses MediaWiki search). fixableWithoutRescrape=true: fix simulation against the EXISTING index shows union of all 27 'fire*' keys = 229 ids and recalls 火球术/火球符文/焰龙兽; the proposed always-merge exact+prefix change in search.js query() needs no index rebuild and no rescrape. Files: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js (lines 427-448), C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.html (line 348), C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index\shards\w_f.js, w_d.js.

---

### [search/SRCH-7] P3 — 结果数被 50 上限静默截断 — '法师' 实际匹配 846 条,UI 显示 '50 条结果' 且无分页/提示

**Evidence**

search.js 第 403 行 limit=50、第 500 行 ranked.slice(0,limit),query 不返回总数;buildUI 第 689 行 status.textContent = rs.length + ' 条结果',第 585-587 行汇总条同样用 rs.length。实测:'法师' 真实候选 846 → 显示 '50 条结果';'治疗' 1,711 → 50;'巨龙' 290 → 50。类型筛选 chip 的计数也只统计 top50,用户点 '专长' 筛选时会误以为全wiki只有几条匹配。原生 wiki 搜索显示总数并分页。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js

**Fix spec**

search.js:query() 返回 {results, total: ranked.length}(或在结果数组挂 total 属性,保持向后兼容);buildUI 状态栏改为 total>limit ? '显示前 50 / 共 '+total+' 条' : total+' 条结果';可选加 '加载更多' 按钮以 limit+=50 重查(分片已缓存,代价仅重排序)。

**Verifier note**: 复现成功，数字逐一吻合。方法:(1) 通读 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js 核对所有引用行号——L403 `const limit = opts.limit || 50;`、L500 `return ranked.slice(0, limit)`(query 只返回截断数组,不带 total)、L687 UI 硬编码 `query(v, {limit:50})`、L689 `status.textContent = rs.length + " 条结果"`、L585-587 汇总条同用 rs.length、L591/597 类型 chip 计数仅基于 top-50 分组,全部属实;全文件无分页/加载更多/截断提示。(2) 写 $env:TEMP\srch7_verify.py 离线复刻 query() 全管线(CJK bigram 切分→md5 首字节分桶→加载 _wiki_full_v2\index\shards\b_XX.js 倒排表→与 titles.js 37,097 条标题子串匹配求并集):'法师'(桶71) posting=846, 标题子串=57(全含于倒排), candidates=846→UI 显示 50;'治疗'(桶29)=1,711→50;'巨龙'(桶2e)=290→50。三个数字与待核查发现完全一致。isOurs=true:search.js/index 全部由 build_search_v2.py 自产,非 wiki 语料;把截断后的 50 标注为"50 条结果"且 chip 计数失真是构建层 UI 缺陷(原生 MediaWiki 搜索有总数+分页,live 站被 403 无法对照,但即使不对照原生,标签本身也是误导)。fixableWithoutRescrape=true:完整 ranked 候选数组在 slice 前已在内存(L500),只需 search.js 单文件 JS 改动(query 返回 total、状态栏改"显示前 50 / 共 N 条"、可选 limit+=50 加载更多——分片缓存于 _bgShards/_wShards,重查代价仅重排序),不动任何语料/索引数据。修复设想技术上成立。

---

### [search/SRCH-8] P3 — 内容命中档排序被标题长度罚分主导,入链热度 tiebreaker 几乎失效 — 2 字标题(pop 3)恒压 3 字标题(pop 692)

**Evidence**

search.js 第 482 行 score -= Math.min(50, title.length) 使内容命中档(基础 0+5)的分数完全由标题长度决定:实测 '火球术' 查询内容档排序为 伊娜(3分,pop523)/祭司(3,pop17)/镜影(3,pop3) 全部压过 塞恩蕾(2,pop692)/达哈克(2,pop659)/火巨灵(2,pop68);pop 仅在标题等长时生效。build_search_v2.py 注释(第 363-366 行)设想的 '战士 beats 战士专长' 场景实际只覆盖同长度标题;对真正的内容相关性(如火球术查询中 火巨灵 比 镜影 相关)长度罚分是反向信号。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\search.js

**Fix spec**

search.js 评分:长度罚分仅应用于标题命中档(score>=200 时再减长度,用于区分 '法师' vs '法师变体'),内容命中档(无标题命中)改为 score += Math.min(20, Math.round(Math.log2(1+popVal)*3)) 直接折入热度,使高入链页(塞恩蕾 692、火巨灵 68)上浮;保留现有 pop 次级比较器作为残余 tie-break。

**Verifier note**: 复现成功,数字逐位吻合。方法:写 $env:TEMP\srch8_repro.py 在 Python 中逐行模拟 search.js 的 query() 评分(bigram 分片求交+标题子串并集+评分排序),数据用真实索引 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\index\{titles.js(37097 items+pop), shards\b_42.js, b_de.js}。结果:查询'火球术'→火球(107 postings)∩球术(85)=82 候选;排序为 火球术(1002,pop113) > 伊娜(3,pop523) > 祭司(3,pop17) > 镜影(3,pop3) > 塞恩蕾(2,pop692) > 达哈克(2,pop659) > ... > 火巨灵(2,pop68,第10位),与发现完全一致。结构性证明:内容档 2 字 ns0 标题最低分 3 > 3 字最高分 2,故 pop=3 的镜影恒压 pop=692 的塞恩蕾——长度罚分(search.js 第482行 score -= Math.min(50,len) 无条件应用于含 0 基分内容档)跨长度组完全压制 pop 比较器(第494-498行仅在分数全等时生效)。build_search_v2.py 第362-366行注释属实,且其'战士 vs 战士专长(2e)'示例实际由 1000/500 标题档区分,从未触发 pop tiebreaker。轻微夸大处:pop 在同长度组内仍有效(len3 组内 692>659>...>68 正确排序),'几乎失效'限于跨长度比较,但核心机制成立。isOurs=true:整套客户端评分是离线镜像自造(live wiki 用 MediaWiki 服务端搜索)。fixable=true:纯 search.js 评分逻辑改动,pop 数组已在 titles.js v2 payload 中,无需重抓甚至无需重建索引。

---

### [links/LINK-1] P3 — browse-letters 88 既存死链(v0.3.24 遗留)已被存在性守卫修复——现状 0/36,701 死链

**Evidence**

全量核验 28 个字母桶页(browse-A..Z/CJK/_.html, 共 36,701 个条目链接, 逐一 unquote href 并检查磁盘文件): 死链 0 个, 每桶 dead_by={} 空。修复来源是 build_browse_letters_v2.py:167 的构建期存在性守卫 `if not (ROOT / target_dir / f"{safe_title(bare)}.html").exists(): n_skip_unrendered += 1; continue`——metadata.pages 中未实际渲染的标题(解析失败/特殊页/断链重定向)在入桶前被剔除。v0.3.24 的 88 个死链由该守卫加入后消除。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_browse_letters_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\browse-CJK.html

**Fix spec**

无需代码修复。保障条件:管线顺序必须保持 build_v2.py(渲染 pages/)先于 build_browse_letters_v2.py(存在性检查依赖磁盘文件), 该约束已写入脚本 165-166 行注释。可选加固:发布前跑一次 browse-*.html 链接存在性断言(本审计脚本即模板), 死链>0 则 fail build。

**Verifier note**: 复现确认(severity P3,已修复态)。方法:写 $env:TEMP 脚本逐一解析全部 browse-字母桶页,提取 <td><a href> 条目链接,unquote 后查磁盘存在性。结果:22 个桶页(非声称的 28 个——K/N/Q/X/Y/Z 为空被跳过,A-J/L/M/O/P/R-W+CJK+_ 实存),共 36,701 条目链接,死链 0——与声称的 0/36,701 完全一致。守卫代码确在 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_browse_letters_v2.py 163-169 行(存在性检查+n_skip_unrendered),165-166 行有管线顺序注释。加测:1,386 个 letter-nav/面包屑 browse-*.html 交叉链接亦 0 死链。重要 nuance:用当前 metadata.json(40,736 pages)重放分组逻辑,守卫今天触发 0 次(3,668 redirect 跳过,0 unrendered,kept 36,701 与 HTML 完全吻合)——即当前 0 死链并不依赖守卫,所有合格标题均已渲染;"守卫消除 v0.3.24 的 88 死链"的因果归因无法核实(脚本未被 git 跟踪,无历史;88 这个历史数字也无 v0.3.24 产物可查),更可能是底层页面渲染/元数据更新所致,守卫现为防回归保险。isOurs=true:死链(若历史存在)属构建层产物,非 wiki 固有;fixable=true:已在不重抓前提下达成 0 死链。结论同意"无需代码修复",可选的发布前 browse-* 链接断言是合理加固。

---

### [links/LINK-2] P3 — safe_title 在 NTFS 大小写不敏感下产生文件名碰撞——Data:Traits-spirit.json 内容被同名大写变体覆盖丢失

**Evidence**

枚举 metadata 全部 40,736 个标题按 (target_dir, safe_title(bare).lower()) 分组, 真实碰撞 3 组: (1) Data:Traits-Spirit.json(parsed 1,544 字符) 与 Data:Traits-spirit.json(parsed 1,548 字符) 是语料中两个不同页面, 都写入 data\Traits-Spirit.json.html, 后写者胜——磁盘文件 canonical=https://pf2.huijiwiki.com/wiki/Data%3ATraits-Spirit.json, 即小写变体内容在镜像中不可达, 指向它的链接静默落到大写变体; (2) 'WOI'/'WoI' 均为重定向→《不朽之战》, 两 stub 内容相同, 无害; (3) '"疑点"洞悉'(safe_title 剥引号)与'疑点洞悉'同名, 但前者是指向后者的重定向源且二者均在 existing_titles 中(build_v2.py:1041-1043 跳过), 磁盘为真实页面, 无害。redirect stub 与真实页面的大小写碰撞: 0。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\data\Traits-Spirit.json.html

**Fix spec**

build_v2.py main() 构建 title_index 的循环(866-879 行)中加碰撞检测: 以 (target_dir, safe_title(bare).casefold()) 为键登记 owner; 检测到第二个不同标题映射到同键时, 为后者生成消歧文件名 safe_fn + '~' + sha1(full_title)[:6], 写入 title_index[t]。同时 render_page_html 第 657 行 `safe_fn = safe_title(bare_title)` 改为优先查 title_index[title](当前是独立重算, 不感知消歧), 确保渲染输出文件名与链接重写一致。rewrite_links/build_categories_block/render_category_members/browse 构建器均从 title_index 取名, 自动跟随。

**Verifier note**: REPRODUCED IN FULL. Method: (1) loaded metadata.json (40,736 pages) and re-enumerated all titles grouped by (target_dir, safe_title(bare).casefold()) using build_v2.py's own determine_target_dir/safe_title via import — got exactly 3 collision groups, matching the claim. (2) Harmful group: Data:Traits-Spirit.json (pageid 55092) and Data:Traits-spirit.json (pageid 54479) are BOTH non-redirect ns3500 pages; full corpus scan (37,098 files) located both: parsed\c8\f711dfe9e3ae2b06cf04969ea699b12629269f.json (1,544 chars, ID 737, 来源 PC, 原文 "Spirit") and parsed\45\ee8613e63db962c4dfc59530bd5a8967fc55d8.json (1,548 chars, ID 773, 来源 MC, 原文 "spirit") — sizes exactly match the claim and the records are substantively different (different trait ID and source book). (3) On disk only ONE file exists: _wiki_full_v2\data\Traits-spirit.json.html (17,289 bytes; NTFS preserved the first writer's lowercase filename) whose content canonical = https://pf2.huijiwiki.com/wiki/Data%3ATraits-Spirit.json — i.e., capital-S content won, the MC spirit record (ID 773) is absent/unreachable in the mirror. (4) Other 2 groups harmless as claimed: WOI/WoI are both redirects to 《不朽之战》 (verified in redirect_map; identical stub target); 疑点洞悉 disk file is the real page (canonical=疑点洞悉, no meta-refresh) because build_v2.py:1041-1043 skips stub generation when src is in existing_titles. (5) Stub-vs-real case collisions across the full 5,799-entry redirect_map: 0, as claimed. (6) Code confirms no case-collision handling: build_v2.py:866-879 title_index loop only resolves cross-namespace bare-title collisions by ns priority; safe_title (lines 81-84) does no case disambiguation; render_page_html line 657 independently recomputes safe_fn with no collision awareness — the proposed fix locations are accurate. isOurs=true: MediaWiki is case-sensitive (both pages legitimately coexist on the wiki); collapsing them on case-insensitive NTFS is a build-layer defect. fixableWithoutRescrape=true: both pages' full parsed HTML exists in the local corpus, so a build-side disambiguated filename (e.g. suffix hash) regenerates the lost page from local data only. Severity P3 is fair: single ns3500 data page affected, and its visible Chinese description text is identical to the surviving variant (only ID/source/English-case fields differ), so user-visible impact is minimal.

---

### [links/LINK-3] P3 — 226 个绝对 URL 的 action=edit/veaction=edit/action=history 链接未被改写层处理——点击经 external_links.js 弹默认浏览器后撞 Cloudflare 403

**Evidence**

全量扫描 built 页: 219 个文件含 226 个 `href="https://pf2.huijiwiki.com/index.php?title=...&(ve)action=edit|action=history"` 锚(如 pages 中崔玛伊克辛/卡戎/亚玻伦的 action=edit, 阿波罗盖‧斯戎二世的 action=history)。成因: build_v2.py rewrite_links 167-171 行 else 分支 `if href.startswith("http") and "huijiwiki.com" not in href` 只给非 huijiwiki 外链加 external 标记, huijiwiki 绝对链接原样保留且不参与本地改写; 运行时 external_links.js isExternal() 对任何 http(s) 都拦截并 open_external → 离线用户被带到被 CF 403 屏蔽的在线 wiki 编辑页。除此之外绝对 huijiwiki 内容链接为零: `<a href="https://pf2.huijiwiki.com/wiki/..."` 在正文中 0 处(40,388 处全部是 <link rel=canonical>), 页脚署名链接 40,441 处属有意设计。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\external_links.js

**Fix spec**

build_v2.py rewrite_links else 分支(167 行起)新增前置判断: `if re.search(r'https?://[^"]*huijiwiki\.com/index\.php\?[^"]*(?:ve)?action=(?:edit|history)', href): a.replace_with(a.get_text()); continue`(保留可见文字, 去掉死交互)。顺带可未来加固: 绝对 `https://pf2.huijiwiki.com/wiki/<title>` 链接走与 /wiki/ 相对链接相同的本地解析(当前 0 例, 防新语料引入)。

**Verifier note**: 复现成立,数字精确一致。方法: 写临时脚本全量扫描 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2 下 44,100 个 HTML — 命中 219 文件/226 个 href="https://pf2.huijiwiki.com/index.php?title=...&(ve)action=edit|action=history" 锚(edit 213 + history 13),与发现的 219/226 完全吻合;抽查实例全部属实(pages\亚玻伦.html ×2、卡戎.html ×2、崔玛伊克辛.html ×2、阿波罗盖‧斯戎二世.html L273 action=history)。成因链亲自核对: build_v2.py rewrite_links L167-172 else 分支仅对 "huijiwiki.com" not in href 的外链加 external 标记,huijiwiki 绝对链接 continue 原样保留;assets\external_links.js L11-17 isExternal() 对一切 http(s) 返回 true(只排除 127.0.0.1/localhost),点击即 open_external 弹默认浏览器撞 CF 403。旁证亦复现: 正文绝对 /wiki/ 锚 0 处(唯一 1 处在 assets\_native_sample_page.html 参考资产),~40,389 处绝对 URL 全是 <link rel=canonical>(发现称 40,388,差 1 可忽略)。isOurs=true 的理由: href 虽源自 ground-truth 语料(parsed JSON parse.text 中可检到同样的 action=edit/history 模板链接,如"帮助翻译这篇文章"/"编辑它"),即链接本身 wiki 固有;但 live wiki 上它们是可用交互,镜像里是我们的 external_links.js 把它们误判为外链并主动弹浏览器制造 403 体验,且 rewrite_links L169 已显式把 huijiwiki 链接从外链标记中豁免(表明改写层认领了 huijiwiki 链接的处理责任)却未做任何处置——属构建层处理缺口,与 RC7(meta-refresh 机制固有但闪屏算项目问题)同类判法。fixableWithoutRescrape=true: 锚的可见文字已在 built HTML 内,修复只需在 rewrite_links 对该类 href 执行 a.replace_with(a.get_text())(与 L182-183 既有图片链接去壳模式一致)后用本地语料重建,零网络依赖。severity P3 合理(226/44,100 文件,均为模板装饰性交互链)。

---

### [links/LINK-4] P3 — 7 个含特殊字符的 metadata 标题无对应磁盘文件——全部因未入抓取语料(37,097 parsed < 40,736 metadata), 非映射缺陷

**Evidence**

枚举 metadata 中含 / : ? * " & + ' 等特殊字符的标题共 6,438 个, 逐一按 build 映射(safe_title: ':'→'_', '/'→'__', 剥 *?"<>|)检查磁盘: 仅 7 个缺失——Cite/The Mwangi Expanse, 怪物能力/输出, 戍卫印记/戍卫印记, 模块化(B/P/S)（特征）, 模块化(P擒拿/S横扫)（特征）, 生物子类/兰花螳螂, 生物子类/海驹; 7 个全部不在 parsed 语料中(0 个已解析却未渲染), 链接指向它们时被 rewrite_links 正确标 class="new" 红链。quote()→unquote() href 编码往返 0 失配。即特殊字符 href→文件名映射本身 100% 一致, 缺口纯属语料未抓全。

**Files**: C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py

**Fix spec**

无映射层修复点。这 7 页属于已知的 metadata(40,736)与 parsed(37,097)差额, 下次链式增量更新抓到后自动渲染恢复; 可把这 7 个标题加入增量抓取的优先补抓清单。

**Verifier note**: 表层证据全部复现，但根因归因与"无法本地修复"结论被推翻。复现方法:写临时脚本($env:TEMP)加载 metadata.json(pages=40,736, 复现)、按 build_v2.py 的 safe_title/determine_target_dir(行81-133)逐题查盘、全量扫描 parsed\*\*.json(37,097, 复现)。结果:特殊字符标题按 bare title(剥 ns 前缀后)计 6,438 个(精确复现, 全标题口径则为 18,034);缺盘恰为同样 7 个标题;7 个均不在 parsed;全语料 0 个"已解析未渲染";映射层确实 100% 一致。【推翻点1·根因】7 个全部 is_redirect=True 且不在当前 redirect_map(5,799 条)——而 redirect 页本来就不靠 parsed 语料落盘, 是靠 redirect_map 生成 stub(metadata-parsed 差额 3,639 中约 3,551 个就是这样落盘的)。当前 metadata.json 的 redirect_map 比本地备份 pf2wiki-scraper\out_v2\metadata_backup_20260519_2222.json(5,890 条)丢失 93 个键; 全盘核查: ns0 缺盘文件共 88 个(7 个特殊字符只是子集, 与特殊字符无关), 88/88 的重定向目标都在备份 redirect_map 里(如 模块化(B/P/S)（特征）→模块化（特征）, 戍卫印记/戍卫印记→守望印记/戍卫印记), 其中 4 个指向模板: ns(已知不在语料, 可接受), 其余 84 个中 81 个目标页现已在盘。即根因是我们管线的 redirect_map 回退(5,890→5,799), 不是"语料未抓全"。【推翻点2·红链断言为假】build_v2.py 行 867-879 title_index 由 metadata 全量 pages 构建, 含这 7 题, 故 rewrite_links(行 191-194)走 entry 分支、不加 class="new": 实测 pages\勺子枪.html 等 8 个武器页 + pages\折叠巨镰.html 共 9 个正文锚 <a href="../pages/模块化(B__P__S)（特征）.html">(无 class)——是"正常蓝链指向不存在文件"的静默死链, 非红链。【修复(无需重抓)】从 metadata_backup_20260519_2222.json 合并回丢失的 93 条 redirect_map 后重跑 build_v2.py 即可恢复 81-84 个 redirect stub(覆盖全部有入链的死链页); 顺带可让 rewrite_links 对"在 metadata 但文件不存在"的目标补 class="new"。涉及: C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json / metadata_backup_20260519_2222.json; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py。

---

### [visual/VF1] P0 — rewrite_links 把所有 a.image 包裹的 <img> 整体删除 — 3,062 页丢失 9,118 张内容图(怪物立绘/职业代表角色/书封/边栏图标)

**Evidence**

build_v2.py rewrite_links() L179-184: 链接目标匹配图片扩展名时执行 `a.replace_with(a.get_text())`，而 <a class="image" href="/wiki/文件:X.webp"><img …></a> 的 get_text() 为空 ⇒ 锚点连同子 <img> 一起被删（且发生在 rewrite_images() 修 src 之前）。全语料统计(正则 <a href="/wiki/*.png|jpg|webp…" class="image"><img)：3,062 个 ns0 页、9,118 张图将被删。逐页核验：食人魔战士 语料 7 img → built 4(img.monster-portrait Ogre_Warrior.webp 在 built 页 grep 0 命中)；至古圣天龙 21→12；死灵师 10→4；法师 9→8(Iconic_Ezren.png 职业立绘消失，浏览器 .floatright img=false)；《核心规则书》 3→2(Core_Rulebook.jpg 书封消失)；战士 5→4。连带效应：已修复的图片 lightbox 在这些页面无大图可放大(浏览器实测 至古圣天龙 剩余 img 最大 32px，<60px 阈值全部跳过)。被删图样本均已在本地镜像(manifest 3,403 条 + _wiki_full_v2\images\ 实体文件均存在：Ogre Warrior.webp / Iconic Ezren.png / Core Rulebook.jpg / 宝藏奖励.png / 建议规则.png)，重建即可恢复。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\食人魔战士.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\法师.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\《核心规则书》.html

**Fix spec**

build_v2.py rewrite_links() L181-184 改为：目标是图片文件名时，若 a.find('img') is not None 则 a.unwrap()(保留 img，让后续 rewrite_images() 正常本地化 src；可顺带把 href 指向 manifest 的 ../images/<local> 以保留点击行为)，仅纯文本锚点才 a.replace_with(a.get_text())。重建后断言：食人魔战士.html 含 img.monster-portrait、8 个抽样页 img 数与语料一致(允许 v2-missing-image 占位)。

**Verifier note**: CONFIRMED P0. (1) Code: build_v2.py L181-184 — image-extension link targets hit `a.replace_with(a.get_text())`; for `<a class="image"><img …></a>` get_text()=='' (alt is not a text node) so anchor+img are deleted, and L584-585 shows rewrite_links() runs BEFORE rewrite_images(), so the imgs never reach src localization. (2) Corpus stats independently reproduced by simulating the build's own target-extraction logic over all 37,098 parsed JSONs: 3,061 ns0 pages / 9,125 imgs inside image-target anchors (claim 3,062/9,118 — same magnitude, regex-detail variance). (3) All 6 sample pages match exactly (corpus_total − anchored == built img count): 食人魔战士 7−3=4, 至古圣天龙 21−9=12, 死灵师 10−6=4, 法师 9−1=8, 《核心规则书》 3−1=2, 战士 5−1=4. grep 'monster-portrait' = 0 in built pages\食人魔战士.html while corpus JSON (parsed\ef\14e45d2cf29d0d42873539a67462509f0de1e7.json) shows `<a href="/wiki/文件:Ogre_Warrior.webp" class="image"><img … class="monster-portrait">`. Residual 'Ogre Warrior'/'Core Rulebook' strings in built HTML are unrelated (Data: edit link + external AoN/pathfinderwiki links), not images. isOurs: the wiki's official rendered HTML contains these imgs; deletion is purely a build-layer transform bug. Fixable without rescrape: manifest (pf2wiki-scraper\out_v2\images\manifest.json) has 3,403 entries, 3,029 with local files all present in _wiki_full_v2\images\; direct lookup shows 9,024/9,125 (98.9%) of the deleted imgs have locally mirrored files (incl. Ogre Warrior.webp / Iconic Ezren.png / Core Rulebook.jpg / 宝藏奖励.png / 建议规则.png); the 101 uncovered (mostly Npx- thumb name variants like 540px-Book_of_the_Dead.png) fall back to the build's standard v2-missing-image placeholder. Proposed fix (a.unwrap() when a.find('img'), only pure-text anchors get replace_with) is sound; rebuild restores images.

---

### [visual/VF2] P1 — 特征 chip 内链接文字几乎不可读 — .tag 强制白字只作用于 span 本体，<a> 仍是琥珀色压在内联深色 chip 底上(约 8,216 处/最多 ~6,800 页)

**Evidence**

_v2_compat.css L1695-1702 `.mw-parser-output .statblock .tag {color:#fff !important}` 不会继承给链接元素；chip 内 <a> 走全局链接色。浏览器实测(食人魔战士, 浅色模式)：chip 背景 rgb(59,123,89)(内联)、chip 文本 #fff、但链接 computed rgb(179,102,0)(#b36600) — 琥珀压绿对比度≈1.2:1，压默认棕 rgb(152,81,61)≈1.7:1，基本不可读；维基原生 chip 链接为白字(我方 1695 行注释亦自证白字意图)。规模(全语料内联 chip 背景计数)：rgb(152,81,61) 4,616 处/3,585 页；rgb(59,123,89) 1,613 处/1,595 页；rgb(0,38,100) 1,706 处/1,352 页；rgb(84,22,110) 281 处/267 页。暗黑模式链接为 #6cb6ff，压绿 chip≈2.3:1 同样偏低。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\食人魔战士.html

**Fix spec**

在 _v2_compat.css L1702 后追加：`.mw-parser-output .statblock .tag a, .mw-parser-output .traits .tag a, .mw-parser-output .tag.trait a { color:#fff !important; }`(必要时补 :link/:visited 提高特异性压过 body.dark p a:link 系列)。

**Verifier note**: 复现成立，且实际比原报告更严重。复现方法+关键数据：(1) CSS 机制：C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css L1695-1702 确认 `.mw-parser-output .statblock .tag {color:#fff !important}` 只命中 span；遍历 style.css 的全部 9 个 @import（_v2_palette/wiki_native/topnav/_v2_compat/wikitable_polish/_fmt_navbox/_fmt_tables/_fmt_mobile/_components）确认全链路无任何 `.tag a` 规则。链接琥珀色来源是 wiki_native.css 的裸 `a{color:#b36600}`（细节修正：不是 `p a` 规则——chip 全在 <div> 内不在 <p> 内，但颜色值相同，与原报告浏览器实测 rgb(179,102,0) 一致）；暗黑模式 _v2_compat.css L800 `body.dark a{color:#6cb6ff}` 亦确认。(2) 规模：扫描 28,514 个 pages\*.html，四色内联 chip 背景计数与原报告逐项全等——rgb(152,81,61) 4,616 处/3,585 页、rgb(59,123,89) 1,613/1,595、rgb(0,38,100) 1,706/1,352、rgb(84,22,110) 281/267，合计 8,216 处、并集 6,262 页（原报告"最多~6,800"为上界，相容）；另有遗漏的第五色 rgb(87,98,147) 186 处。(3) 加重情节：8,400/8,400（100%）内联背景 chip 的可见文字全部包在 <a> 内，故强制白字规则在这些 chip 上一个字都没涂到，整个 chip 文字均为琥珀压深底；复算对比度 #b36600 压绿 1.16:1、压棕 ~1.35:1、压海军蓝 ~3.2:1，暗黑 #6cb6ff 压绿 2.35:1，全部低于 WCAG 4.5:1。(4) 归属：wiki_native.css（站点 CSS 镜像）含零条 .tag 样式规则（仅 glyphicon-tag 图标名），即维基原生 chip 样式未进镜像，_components.css L219 与 _v2_compat.css L1697 是我方手写替代层；同文件 L1713-1716 对 .classquote a 单独补了链接色，证明作者知道链接需单独覆盖却漏了 .tag——属我方构建层半成品修复，忠实镜像豁免不适用（我方已主动偏离原生改白字）。唯一保留：原报告"维基原生 chip 链接为白字"无法离线证实（L1695 注释实际说原生 chip 文字是深灰 #333 非白字），但这不影响缺陷归属。(5) 可修性：纯 CSS 追加（.statblock .tag a 等 + color:#fff !important 即可压过无 !important 的 body.dark a 系列），改一个共享 CSS 文件即生效，无需重建页面更无需重抓。已核 JS 资产无运行时改色逻辑。

---

### [visual/VF3] P2 — v0.3.27 statblock 红冠头漏掉 span.line 直挂变体 — 约 26% 的 statblock(≈4,200 页，武器/专长/法术/聚能类)标题行完全无样式

**Evidence**

_components.css L180 签名头选择器 `.statblock > div:first-child` 仅当名称行包在 div 里才命中。随机 1,500 页抽样(语料 16,237 页含 statblock)：1,949 个 statblock 中 499 个(25.6%)首个子元素是裸 `span.line`(无任何 CSS 命中——全资产 grep 'span.line' 只有 L167 注释)，红冠头/金边线/Category 右浮全部缺失。浏览器实测对比：战锤.html firstChild=SPAN.line、行背景 transparent、.name b 仅 14px 普通行内字 vs 食人魔战士 头部 bg #6d2002、白字 18.5px 横幅。同类两种 statblock 在站内观感割裂，且裸标题行弱于维基原生(原生该行有名称加大/等级右对齐)。严格误涂检查：div:first-child 涂错内容的情况为 0(不存在红条压正文)。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_components.css; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\战锤.html

**Fix spec**

为裸变体补一套平行规则：`.mw-parser-output .statblock > span.line:first-child { display:block; background:var(--accent-band); color:var(--accent-on); padding:var(--sp-2) var(--sp-4); border-bottom:3px solid var(--gold); }` + 对应 `> span.line:first-child .name b`(字号/白字)与 `.category`(右浮 pill)与 `.aonlink a` 规则(复制 L187-209 选择器加 span.line 变体)；或在 build_v2.py 渲染时将 .statblock 直挂的 span.line 包一层 div 归一化 DOM。

**Verifier note**: CONFIRMED, and full-corpus scan shows it is slightly WORSE than the sampled claim. Reproduction: (1) CSS audit — _components.css L180-209 header rules all require `.statblock > div:first-child`; grep across all of _wiki_full_v2 assets finds exactly one `span.line` occurrence (the L167 comment), and wiki_native.css (403,358 bytes, the live load.php dump) contains ZERO `statblock` or `quote-block` rules, so no other sheet rescues the bare variant. (2) Full scan of all 28,514 built HTML in _wiki_full_v2\pages (temp script, no sampling): 16,237 pages contain statblock (exact match to claim), 20,922 statblock divs total; first-child breakdown: div 11,839 (56.6%), bare span.line 5,504 (26.3% — claim's 25.6% sample estimate confirmed), across 4,740 distinct pages (claim said ≈4,200, an undercount). (3) Browser verification (Playwright vs localhost:8753): 食人魔战士.html div-variant header = bg rgb(109,32,2), white text, 2.67px gold border-bottom, .name b 19px white, .category float:right with pill bg; 战锤.html span.line-variant = transparent bg, no band/gold rule, .name b 14px, .category float:none no pill — matches claimed measurements. One overstatement to correct: the bare variant is not literally "无任何 CSS 命中" — _v2_compat.css L725-754 (`.statblock .name`) gives its name span 10px left-padding + hairline border-bottom + dark-red color, and `.statblock b` (L217) tints the bold name; but the entire signature header (band/gold rule/display font/category pill/aonlink treatment) is absent, so the substance stands. isOurs: yes — corpus ground truth (parsed\c8\5bac3300...json, title 战锤) shows the bare span.line DOM is wiki-native with no inline <style>, but the red crown header is our own v0.3.27 "SIGNATURE COMPONENT" design in _components.css; we styled only the div-wrapped variant, creating an intra-site inconsistency the original wiki did not have. fixableWithoutRescrape: yes — pure CSS addition (parallel `> span.line:first-child` ruleset) or build_v2.py DOM normalization; fix safety verified: 100.0% of the 5,504 bare span.line first-children contain both span.name and span.category (genuine headers, zero misfire risk). Caution for the fixer: do NOT extend the rule beyond span.line — the scan found other first-child variants (2,312 start with <b>, 928 text-only, 289 <p>, 43 <i>) that are label-first affliction/quote blocks without name headers; banding those would be wrong. Key files: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_components.css (L164-229), C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css (L713-754), C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\战锤.html, C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\食人魔战士.html.

---

### [visual/VF4] P2 — 暗黑模式未适配的内联样式族：纯蓝 强/弱 评级字(1,481 页)、奶油底浮窗面板(130+8 页)、无类名深绿字(225 处) — CSS 无任何 [style*=] 兜底

**Evidence**

全部资产 CSS 中 [style*=…] 属性选择器命中数为 0(唯一例外 .intro[style])，暗黑只靠类名 !important 覆盖，无类名/无钩子的内联样式原样渲染。全语料内联颜色分布统计+浏览器实测(html.dark)：(a) `<span style="color:blue">弱</span>` 防御/攻击评级标记 12,050 处/1,481 个生物页，computed rgb(0,0,255) 压深底 #2a2218 对比≈1.6:1 不可读(实测 至古圣天龙)；color:red 9,650 处/3,077 页≈3.2:1 勉强。(b) div.hidden-sm.hidden-xs 右浮说明面板 `background-color: rgba(233,222,208)` 130 页(法术列表/N环、载具、材料、神话专长…)，暗黑实测 bg rgb(233,222,208)+文字 rgb(230,228,225)≈1.1:1 完全不可读(实测 法术列表/1环)。(c) 首页 3 块无类名 div `rgb(245,239,224)`(最新公告/最近编辑/最近评论)同症状(实测 pages\首页.html，共 8 页 21 处)。(d) 无类名 th/div `color:#004416` 深绿字 225 处(th 158 + div 59 + div.bg-primary 8，集中在书目/AP 页)暗底上≈1.5:1。注：infobox/sidebar/classquote 等带类名的内联色已被现有 !important 规则正确压制，未列入。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\首页.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\法术列表__1环.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\pages\至古圣天龙.html

**Fix spec**

在 _v2_compat.css 暗黑段追加属性选择器兜底：`body.dark .mw-parser-output [style*="color:blue"]{color:#7aa7ff!important}`；`body.dark .mw-parser-output [style*="color:red"]{color:#ff8a8a!important}`；`body.dark .mw-parser-output div[style*="233,222,208"], body.dark .mw-parser-output div[style*="245,239,224"], body.dark .mw-parser-output div[style*="237,227,200"]{background:var(--card)!important;color:var(--fg)!important}`；`body.dark .mw-parser-output th[style*="color:#004416"], body.dark .mw-parser-output div[style*="color:#004416"]{color:var(--gold)!important}`(注意排除 background:#004416 的命中，可用 [style*="color:#004416"] 精确串)。

**Verifier note**: 核心发现成立，但 (d) 子项被推翻，须从修复范围剔除。复现方法+关键数据：

【CSS 兜底缺失——证实】全 12 个资产 CSS 中 grep `style*=` 命中 0；`[style` 仅命中 _v2_compat.css:990 `body.dark .intro[style]` 和 wiki_native.css 内 `.skin-huiji-dragonhide [style="border:5px dotted #A1FB00…"]` 精确匹配选择器（dragonhide 类我们的页面/theme.js 从不施加，等于死代码）。暗黑=theme.js 往 body/html 加 .dark + _v2_compat.css 182 条 body.dark 类名规则，无任何内联样式兜底。无 catch-all（dark 段唯一裸元素规则是 div.intro）。

【(a) 蓝/红评级字——精确复现+实测】遍历 pages\ 28,514 个 HTML：style 含 color:blue 12,050 处/1,481 页（与声称完全一致）；color:red 9,661 处/3,077 页（声称 9,650，差 0.1%）。Playwright 实测 至古圣天龙.html 强制 body.dark：span"弱" computed rgb(0,0,255)，有效背景 rgb(38,36,31)，对比 1.8:1（WCAG 需 4.5:1），不可读。成立。

【(b) 奶油浮窗——精确复现+实测】div.hidden-sm.hidden-xs 含 233,222,208 恰好 130 页（与声称一致）。实测 法术列表__1环.html 暗黑：面板 bg 保持 rgb(233,222,208)，文字被暗黑规则改成 rgb(230,228,225)，对比约 1.05:1，完全不可见。成立。其余 438 页的 233,222,208 命中全在 div.quote-block.statblock/table.infobox 上，已被 _v2_compat.css:495-530 !important 压制，无需处理。

【(c) 首页族——复现】rgb(245,239,224) 共 8 页（首页.html 3 处、临时首页.html 等），机制同 (b)。另确认 fix 设想提到的 237,227,200 存在于 49 页。成立。

【(d) #004416 深绿字——推翻】声称的"th 158 + div 59 = 深绿字"全部是子串误报：这 158 个 th 的 style 实为 `background-color:#004416; color: white`（"background-color:#004416" 包含子串"color:#004416"），59 个 div 同理 `color:white; background-color: #004416`，8 个 div.bg-primary 也是 background-color——全是白字绿底，暗黑下本就可读，无需修。真正的 color:#004416 文字命中是 th.infobox-label 1,118 + td.infobox-data 1,118（共 2,236 处，均带类名、位于 table.infobox 内），已被 _v2_compat.css:523-530 `body.dark .infobox td/th { color: var(--fg) !important }` 完整压制（脚本验证 158 个"无类名 th"的外层 table 100% class="infobox"，亦被同规则覆盖）。且原修复设想的 `[style*="color:#004416"]` 会匹配无空格写法的 `background-color:#004416`（158 th + 8 div.bg-primary），把白字改金字反而引入回归——(d) 选择器必须整条删除。

【判定依据】isOurs=true：内联样式是维基原文，但暗黑主题纯属构建层自造（theme.js+_v2_compat.css），亮色模式下一切正常，缺陷只在我们的 dark 层；维基原生 dragonhide 暗皮肤甚至自带 [style=] 处理，反证此类适配是暗色主题应尽义务。fixableWithoutRescrape=true：纯 CSS 追加（blue/red 兜底 + 233,222,208/245,239,224/237,227,200 三个 bg 串兜底），不动语料。severity P2 合理。涉及文件：C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css（修复落点）、assets\theme.js、assets\pf2_theme.css:114（--card:#2a2218）；复现脚本 $env:TEMP\vf4_scan{,2,3,4}.py。

---

### [visual/VF5] P2 — [确认已知 P2] README/关于页暗黑下 .well 左侧强调边框被压成灰色 — 一行修复

**Evidence**

README.html L43 内联 `border-left:4px solid var(--accent)`；_v2_compat.css L998-1005 `body.dark .well { border-color: var(--border,#3a3a3a) !important }` 把四边一起覆盖。浏览器实测(README.html, dark)：borderLeftColor computed rgb(59,55,51)，背景 rgb(38,36,31)，强调条视觉消失；浅色模式正常为 accent 红。

**Files**: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\README.html; C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css

**Fix spec**

在 _v2_compat.css L1005 之后追加一行：`body.dark .well { border-left-color: var(--accent, #c1453d) !important; }`。

**Verifier note**: 复现确认 + 修复方案已实测有效。方法：(1) 文件核对 — C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\README.html L43 确有 <p class="well" style="padding:10px 14px;border-left:4px solid var(--accent)">；assets\_v2_compat.css L998-1005 确有 body.dark .well { border-color: var(--border,#3a3a3a) !important }（border-color 四边 shorthand，!important 击败内联普通声明）。style.css L39/L42 依次 @import _v2_palette.css 与 _v2_compat.css，链路成立。(2) 变量核对 — _v2_palette.css L143-148 暗色 --card:#26241f、--border:#3b3733、--accent:#d4633a，与声称的 computed 值逐字节吻合。(3) 浏览器复现（Playwright + 本地 http.server:8741 服务 _wiki_full_v2，file:// 被沙箱禁止）：README.html p.well 浅色 borderLeftColor=rgb(109,32,2)(=浅色 accent #6d2002，正常)；加 body.dark 后 borderLeftColor=rgb(59,55,51)(=#3b3733=--border)、background=rgb(38,36,31)(=#26241f=--card)，对比度约 1.3:1，强调条视觉消失 — 与发现声称的数值完全一致。(4) 修复验证 — 在该页注入提议的一行 `body.dark .well { border-left-color: var(--accent, #c1453d) !important; }`（同特异性、后位序，胜出），borderLeftColor 变为 rgb(212,99,58)=#d4633a 暗色 accent，强调条恢复。注意 fallback 应写 #d4633a 而非 #c1453d（#c1453d 是 pf2_theme.css 的 accent，README 走 _v2_palette.css 链路；不过 var 总能解析，fallback 不会触发，无实质影响）。归属：README.html 为手写自造壳页（build_v2.py 不生成它，grep 无 README/使用说明 字样），_v2_compat.css 是我们的兼容层 — 纯构建层缺陷，与 wiki 语料无关。影响面：全站 37k+ HTML 中仅 README.html 1 处使用该内联 accent 左边框（递归 grep 仅 1 命中）；wiki 内容页的 div.well（如 quote-success 引文框）无内联 accent 边框，不受此问题影响。无需重抓，追加一行 CSS 即可。

---


## 否决/备案

### [INT-3] smw-highlighter 工具提示死件——13 页 SMW 警告图标可见但悬停无任何反应,提示文本被 CSS 永久隐藏

复现方法: (1) 全扫 out_v2\parsed 37K JSON → 恰好 13 页含 smw-highlighter(与报告一致,含狱火战靴 c7\efd553b0...json); (2) 全扫 _wiki_full_v2\pages → 13 个对应 HTML(如 pages\狱火战靴__狱火战靴.html); (3) 解析 wiki_native.css(经 style.css @import 加载)确认 .smwttcontent{display:none} 且 .smwtticon.warning{display:inline-block;background:url(data:image/png;base64,...)} 图标离线可见; (4) grep assets\*.js 零命中 smwtt/smw-highlighter/qtip。结构性事实全部成立,但核心断言『悬停无任何反应、提示文本被永久隐藏』被推翻: 报告误读了标记——语料与构建页实际均为 <span class="smw-highlighter" ... data-title="警告" title="“+”不能分配给公开的带值13的数字类型。">,即外层 span 的原生 title 属性携带完整警告文本(『警告』二字在 data-title 而非 title)。可见图标是该 span 的子元素且自身无 title,无任何 pointer-events:none 规则,且全资产唯一的 title 剥离代码 huiji_tt.js:358 只作用于 span.huiji-tt——故悬停图标即触发浏览器原生 tooltip 显示完整警告消息,信息零丢失。与 live wiki 的唯一差异是原生 tooltip 样式 vs SMW qTip 样式浮层(纯外观),且这 13 条『警告』本身是维基自带的 SMW 标注错误,忠实镜像内容。判 isReal=false(所述缺陷不成立)、isOurs=false(残余仅为静态镜像不带 SMW JS 模块的外观级差异+内容为 wiki 固有错误噪声)。若仍想要样式化浮层,fixableWithoutRescrape=true: 文本已在本地 title/data-title/.smwttcontent 三处齐备,约 20 行 JS 即可,无需重抓。

---

### [LINK-5] 核验通过项汇总: 锚点保留/页内 id/TOC/外链拦截覆盖/图片本地化均无改写层缺陷

独立复现确认 [LINK-5] 各项"核验通过"结论成立,改写层无新缺陷。复现方法+关键数据: (1) 全量扫描 44,095 个 built HTML(pages 28,514/category 3,646/data 11,866/project 14/根 55): 根相对 href="/..." 0、协议相对 // 0、file:// 0;不含 external_links.js 的文件恰 3,614 个,全部为 meta-refresh 重定向 stub 且 0 个含 http href——与发现完全一致;assets\external_links.js 源码确认 isExternal 排除 127.0.0.1/localhost。(2) 跨页锚链全量 10,550 条(发现报 10,495,同量级,统计口径含根级文件),落在重定向 stub 上 0 条(精确复现;尽管 build_v2.py rewrite_links L188 仅单跳解析 redirect_map,实测无锚链落 stub)。(3) 独立重抽 200 条锚链(seed 不同于原审计): 184/200 可达(92%,原审计 94%);10 个去重后的失败 target#frag 逐一对照语料(sha1(pageid) 寻址 parsed JSON): 8 个语料 parse.text 同样无该 id——wiki 自身陈旧锚(真实标题 id 带英文后缀,如 惊人的机器_THE_ASTONISHING_ENGINE、战斗祭司_Warpriest、巨龙_DRAGON、第一步：掷D20_Step_1:_Roll_D20),镜像忠实;2 个(法术#聚能法术、惊世奇土#时间线)为已立项 RC1 分类劫持副作用(已验证 惊世奇土 ns0 语料含 id=时间线 但链接被改写指向 category/惊世奇土.html),不另报。(4) 碎片保留: 抽 60 个语料源页 129 条 /wiki/X#frag 链 → built href 中 129/129 保留 fragment。(5) TOC: 抽 80 个含 page-toc-v2 页共 579 锚,0 不可达。(6) 图片: 抽 300 个含图页 856 个 ../images/ src 全部存在于磁盘;真实远程 <img src> 0(原始全量扫描出的 16,401 个 src="http 命中均为惰性 data-original-src 簿记属性的子串误匹配,非缺陷);srcset 0、data-src 0;空 src 恰 4 个 <img>(分布 3 文件)且全为 class="v2-missing-image" 设计内占位;manifest.json 3,403 项/374 项无 local——两数精确吻合。对抗性补查未发现新缺陷: 40,388 页的远程 <link rel="canonical"> 为不触发网络请求的元数据;40,441 个 huijiwiki <a> href 为设计内页脚源站链接+wiki 固有 interwiki(extiw)链接,均被 external_links.js 按外链拦截;唯一新观察为 project/编写规范.html 中 1 条锚链指向不存在的 特殊_跨wiki(Special 命名空间页,非文章,wiki 机制固有,非改写层缺陷)。结论: 本发现为"无缺陷"核验汇总,证据可复现(isReal=true);不存在我方构建层缺陷(isOurs=false);无需修复故 fixable=false。建议采纳其"将五个临时审计脚本固化为发布前回归检查"的设想。涉及文件: C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\build_v2.py (rewrite_links L136-213); C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\external_links.js; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\images\manifest.json; C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out_v2\metadata.json。

---

### [VF6] [回归核验通过项备案] TOC 右栏/标题锚/桌面宽度表格溢出均正常；图片 lightbox 机制本身正常但受 VF1 拖累无大图可放

复现方法：python -m http.server 8741 于 _wiki_full_v2 根目录 + Playwright 实测（1600x900/1200/900 视口）+ 静态 grep/读源码。VF6 为"回归通过项备案"，全部声明均独立复现成立，且其中一处残留问题已比备案时更好。(1) TOC 右栏：法师.html 中 div.page-toc-v2 确为 .layout 第三个 flex 子元素（children=[wiki-sidebar, page-body, page-toc-v2]），computed position:sticky、flex:0 0 250px、top:64px、实测宽 250px，对应 C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\assets\_v2_compat.css 第 600-609 行规则；TOC 30 个锚链接 30/30 可解析（不止首锚）。(2) 标题锚：带 id 的 .mw-headline=34 个，运行时注入 .pf2-anchor=34 个（静态 HTML 中为 0 — 系 JS 注入，与备案口径一致）。(3) 表格溢出：法术列表.html documentElement.scrollWidth-clientWidth 在 1600px 和 1200px 视口均=0px（与备案一致）；900px 视口实测也=0px（备案时为 96px，归 RC5），原因是 _v2_compat.css 第 8 节"Wiki HTML utility shim"（1325-1454 行，.flex-1/.cf-header/.cf-container 等 fallback）已落地，RC5 域残留在该页已消除。(4) Lightbox：window.__pf2LightboxLoaded===true；法师.html 全部 8 张内容图自然尺寸 64-70px 但渲染尺寸仅 25-32px，按 image_lightbox.js 第 24-29 行"显示尺寸<60px 跳过"的设计正确不触发（点击实测不弹层）——备案"条目页无可触发大图"属实；机制本身用注入 200x200 测试图验证端到端正常：点击后 #pf2-lightbox-overlay 弹出、含大图+caption+body overflow:hidden。唯一新发现的微瑕（P4 级，不改变结论）：_v2_compat.css:1317-1319 给 .mw-parser-output 所有 img 设 cursor:zoom-in，包括 JS 会拒绝放大的 <60px 图标，光标承诺与 JS 阈值不一致；属化妆性问题可顺手修。判定：备案证据真实可复现(isReal=true)；所述功能均工作正常、不存在构建层缺陷(isOurs=false)；备案要求的唯一后续动作（VF1 修复重建后对食人魔战士/法师/《核心规则书》复测一次点击放大）纯本地即可完成，无需重抓(fixableWithoutRescrape=true)。

---


## 完备性批评者

[新维度审计结果 — 实测后仅 2 条达到「大概率真有问题」标准,其余候选已实测排除]

【确认-1 | wiki 功能层】随机页面/最近更改/链入页面(Special:Random / RecentChanges / WhatLinksHere)全站零实现 — 原生 wiki 侧栏工具箱标配,镜像的 `_snippets\sidebar_sub.html`(32 行)与全部 `assets\*.js` 中 grep `随机|最近更改|Special:` 均 0 命中(仅 font-awesome glyph 噪声)。验证:`Grep '随机页面|最近更改' C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\_snippets` → No matches;且 `out_v2\metadata.json` 含页面清单+时间戳,随机页面纯前端即可实现,属确定性功能缺失而非取舍。

【确认-2 | webfont 资产层】`SourceHanSerifCN(-Bold)` 内联 font-family 出现在 1,002/28,514 个 ns0 页(3.51%,如首页日期框、公理裔族群/德鲁伊/精金龙等装饰标题),但全站唯一 @font-face 是 Pf2Icon(`_v2_compat.css:843`),`assets\native\` 最大字体文件仅 165KB(全为 font-awesome,无 CJK 字体)— 这些元素全部回退系统默认字体,与原生 fs.huijiwiki.com 提供的思源宋体观感不同。验证:`Grep '@font-face' assets\` → 仅 Pf2Icon;`python` 全量扫描 pages\*.html 计数 SourceHanSerif=1,002。

【已实测排除(勿再查)】
- 跨页锚点完整性:抽样 3,000 页共 1,077 条 `#fragment` 链接,50 条缺锚但经语料比对 50/50 均为 wiki 自身坏锚(链接 fragment 缺英文后缀,语料目标页本就无该 id;build 的 legacy 点编码+raw 双锚发射工作正常,build-introduced=0)。
- 图片 hotlink/本地存在性:抽样 4,000 页 6,005 个存活 `<img src>`,远程 0、本地缺失 0(a.image 整体删除已是既报发现)。
- 打印样式:8 个 `@media print` 块已覆盖(topnav/sidebar/footer 隐藏、分页表全行展开、navbox break-inside)。
- 移动断点/视口:页面均有 `<meta name="viewport">` + `_fmt_mobile.css` 存在。
- browse-CJK.html 3.24MB 单页性能:属已立项 RC2(自造 browse-* vs 原生分页清单)范畴,未单独报告。
