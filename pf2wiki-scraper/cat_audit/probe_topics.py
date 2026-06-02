"""Probe the live wiki for a broad set of topic/portal/index page titles, to find
the 出版物-pattern: a real complete wiki page exists that our offline site stubs,
mis-links, or doesn't surface. For each title: exists? redirect (->target)? length
(prose chars). Cached to out_v2/_cat_audit/_topic_probe.json for the audit workflow.
"""
from __future__ import annotations
import json, sys, time, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pfwiki import browser, api_get  # noqa: E402
OUT = ROOT / "out_v2" / "_cat_audit"

TITLES = [
    # axis topics (do these have real articles beyond our derived browse lists?)
    "专长", "法术", "物品", "生物", "族裔", "背景", "变体", "职业", "信仰", "地理",
    "状况", "异常状态", "特征", "动作", "技能", "装备", "武器", "护甲", "盾牌", "宝藏",
    # portal / index pages
    "出版物索引", "出版物", "规则索引", "术语索引", "勘误索引", "创建角色", "升级",
    "内海", "历史", "组织", "派系", "传说故事", "地狱骑士", "GM帷幕", "译名表",
    "信仰综述", "神祇", "祖先", "地点", "怪物",
    # rules portals players look for
    "状态", "持续效果", "环境", "陷阱", "危机", "战斗", "探索", "休整", "死亡",
    "条件", "魔法物品", "仪式", "符文", "法器", "炼金", "诅咒",
    # spell traditions / kinds
    "奥术", "神术", "异能", "原能", "戏法", "聚能",
    # character building portals
    "技能专长", "职业专长", "族裔专长", "通用专长", "原型", "兼职",
]


def main() -> int:
    res = {}
    with browser(headless=False) as (ctx, page):
        # batch titles (API allows up to 50 per query); fetch redirects + length
        for i in range(0, len(TITLES), 40):
            chunk = TITLES[i:i + 40]
            info = api_get(page, {
                "action": "query", "titles": "|".join(chunk),
                "redirects": "1", "prop": "info", "inprop": "",
                "format": "json", "formatversion": "2",
            })
            q = info.get("query", {})
            redirs = {r["from"]: r["to"] for r in q.get("redirects", [])}
            for p in q.get("pages", []):
                t = p.get("title", "")
                res.setdefault(t, {})["resolved_title"] = t
                res[t]["missing"] = bool(p.get("missing", False))
                res[t]["length"] = p.get("length")  # byte length of wikitext
            for frm, to in redirs.items():
                res.setdefault(frm, {})["redirects_to"] = to
                res[frm]["missing"] = False
            time.sleep(0.3)
        # mark which of our requested titles redirect / exist
        out = {}
        for t in TITLES:
            r = res.get(t, {})
            # if t redirected, the resolved page info is under the target title
            tgt = r.get("redirects_to")
            tgt_info = res.get(tgt, {}) if tgt else r
            out[t] = {
                "exists": not tgt_info.get("missing", True) if tgt else not r.get("missing", True),
                "redirects_to": tgt,
                "length": tgt_info.get("length") if tgt else r.get("length"),
            }
    (OUT / "_topic_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    real = sum(1 for v in out.values() if v["exists"] and not v["redirects_to"])
    redir = sum(1 for v in out.values() if v["redirects_to"])
    miss = sum(1 for v in out.values() if not v["exists"])
    print(f"probed {len(out)} titles: real={real} redirect={redir} missing={miss} -> _topic_probe.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
