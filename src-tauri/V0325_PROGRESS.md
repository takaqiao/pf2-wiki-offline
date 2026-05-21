# v0.3.25 批次进度账本

> 用户 2026-05-21 指派(分类修复 v0.3.24 发布后):4 项改进,**全做完再打包发版**(打包等会)。
> 发版仍需用户显式授权(同 v0.3.24)。基准 = 干净 `pf2-wiki-offline_0.3.24_x64-portable`。

## 任务清单
- [x] **#1 职业 hub 修复**: DONE。KNOWN_CLASSES → 27 权威 roster,classes/index.html 27/27 found、27 链接全 resolve、0 placeholder。
- [x] **#3 字母桶死链**: DONE。build_browse_letters_v2.py 改:跳过 redirects(3668)+ 只链已渲染页 + 字母导航只列存在的字母 + 清理孤儿页(删 K/N/X)。全 browse(52 页/95653 链)0 死链,字母导航 0 死链。
- [ ] **#1 职业 hub 修复**(原始描述): `build_class_hubs_v2.py` 的 KNOWN_CLASSES(25,2026-05-20)已过时。**权威 = live 职业页 27 职业**(全部已在离线语料)。纠正:Swashbuckler 斗士→浪客、Kineticist 元素使→御能师、Inventor 发明家→发明家（职业）、**Psychic 灵媒→心能者**(灵媒 现=Animist!)、新增 守护者 Guardian/统帅 Commander/灵媒 Animist/神源者 Exemplar,删 圣武士(非基础职业)。无需重抓。
- [x] **#2 更新进度条**: DONE(代码;exe 待打包时 -RebuildExe)。main.rs `apply_incremental_update` 改为分块下载(ureq 流式 read 65KB/块)+ 发 `update-progress` Tauri 事件(phase=download/verify/apply,含 pct/downloaded/total/patch)。updater_ui.js 加 getListen() + 点「补丁更新」后渲染进度条(黄色填充)+ 阶段文案(下载 i/N x% (MB) / 校验 / 应用中)。cargo check 通过(1m55s,0 错);capability 已含 core:event:default;node --check JS OK。**v0.3.25 发版必须带 -RebuildExe**(有 Rust 改动)。
- [ ] **#2 更新进度条**(原始描述): 用户要"百分比/进度感"。Rust `apply_incremental_update` 下载时按字节发 Tauri 事件 → `updater_ui.js` 渲染进度条+阶段文案。**需 -RebuildExe**(Rust 改动)。
- [ ] **#3 字母桶死链**: browse-CJK(87)+browse-C(1)=88 既存死链(`build_browse_letters_v2.py` 索引了无文章页的标题)。低优清理。
- [x] **#4 首页对齐 live 首页**: DONE。index.html(静态手维护)中心区改为镜像 live 首页分区:规则导航/世界设定/出版物/索引与帮助(`generate_homenav.py` 校验全部 41 链接存在);左栏+统计计数从过时膨胀值(专长11111等)改为修复后真值(专长4872/法术1761/物品3400/怪物1490/职业27/族裔245/信仰474/地理1145/异常状态43);topnav 职业 27;字母网格去掉孤儿 K/N/X。index.html 94 链接 0 死链。
- [ ] **#4 首页对齐**(原始描述): live `首页` 结构 = 规则导航(创建角色/族裔/职业/技能/专长/法术/装备/宝藏)+ 世界设定(内海/历史/信仰/组织/生物/地狱骑士/GM帷幕…)+ 出版物(近期书)+ 索引(出版物/勘误/术语/特征/规则)+ 帮助。重做 `index.html`(链到我们的离线页)。动态块(新闻/最近编辑)离线略去。

## 关键数据(已抓,在 out_v2/_cat_audit/)
- `_roster_english.json`: 27 职业权威 中文→English(已校对页面 intro)。
- `_homepage_live.html` + `_homepage_summary.json`: live 首页结构(44 链接 + 模板分区)。

## 27 职业权威映射(中文 = English,全部离线present)
吟游诗人=Bard 牧师=Cleric 德鲁伊=Druid 战士=Fighter 游侠=Ranger 游荡者=Rogue 女巫=Witch 法师=Wizard 炼金术士=Alchemist 野蛮人=Barbarian 神卫=Champion 调查员=Investigator 武僧=Monk 术士=Sorcerer 先知=Oracle 浪客=Swashbuckler 御能师=Kineticist 灵媒=Animist 神源者=Exemplar 发明家（职业）=Inventor 枪手=Gunslinger 守护者=Guardian 统帅=Commander 奇术师=Thaumaturge 心能者=Psychic 魔战士=Magus 召唤师=Summoner

## 优化项 (用户 2026-05-22 "再看看能优化什么" → "好,全做")
- [x] **#5 browse 分页**: DONE。复用 `assets/wikitable_paginate.js`(自带搜索框+翻页+每页选择+MutationObserver,≥100 行启用)。render_browse_html + render_letter_page 表加 `wikitable` class + 引脚本,删冗余自定义 filterBrowse。browse-all 排除 ns=3500 数据页(37k→~25k)。
- [x] **#6 全分类页**: DONE。build_v2.py 加 [4b] 后处理:为反向索引里所有被引用但未抓的分类合成最小 Category doc 过 render_page_html 生成成员列表页。实测 **+3287 页(category/ 358→3646)**,内容页死链 **3.11%→1.70%**(分类死链基本清除;剩余是文章红链)。
- [x] **#7 topnav 标签**: DONE。_snippets/topnav_sub.html + index.html:神祇→信仰、地点→地理、状态特征→异常状态(桌面+移动菜单)。
- [x] **#8 首页旧数**: DONE。35,469→真实文章数 **24,666**(ns0);搜索框占位去掉旧数变通用;统计段改真实计数(24,666 文章/11,866 数据/3,646 分类)+定性翻译说明(弃旧的 35,317/152)。
- 遗留(未做,低优):内容页剩 1.70% 死链=文章红链(部分是 wiki 本身红链=应死链,部分可能漏抓,需逐个对 live 核实,价值低)。

## 日志
- 2026-05-21 | 建账本;抓 live 首页结构 + 职业 27 权威roster+English(校对页 intro);确认 27 全离线present(无需重抓)。下一步:实现 #1。
- 2026-05-21 | **#1/#3/#4/#2 全部 DONE 并提交推送**(b35d54b 职业、b8a176a 字母死链、9c584f7 首页对齐、本次 #2 进度条)。**4 项全完成,待打包 v0.3.25**(纯内容部分 + #2 的 Rust 改动 → 发版须 `release.ps1 -PrevVer v0.3.24 -NewVer v0.3.25 -RebuildExe`,基准=干净 pf2-wiki-offline_0.3.24_x64-portable;发版待用户授权)。

## 发版清单(打包时)
- 全部从现有 parsed 重建(无需重抓):build_v2 + class_hubs + browse_v2 + browse_letters + search + nav_stubs + dead_stubs。
- bump v0.3.25(_app_version.json/Cargo.toml/tauri.conf.json/Cargo.lock)。
- `release.ps1 -PrevVer v0.3.24 -NewVer v0.3.25 -RebuildExe`(#2 改了 Rust,必须重编 exe)。
- 验证:verify_a/verify_c/deadlink_check 全绿;acl_probe(因重编 exe,值得跑一次确认 ACL/事件 OK)。
