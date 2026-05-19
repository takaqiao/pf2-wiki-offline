"""Traverse every entry in glossary.json and verify EN<->ZH correspondence.

For each mismatch:
  1. Consult the raw wiki extract (out/glossary_wiki.json, 16k+ entries with
     frequency-counted alternatives).
  2. If a wiki candidate passes correspondence, REPLACE the ZH with it
     (wholesale — no per-char editing).
  3. Otherwise DELETE the entry.

Never modifies a ZH string in place. Every action is either wholesale replace
or delete. List-valued (polysemy) entries are left untouched.

Correspondence rules (any failure = mismatch):
  R1 — Truncation: ZH is identical to the ZH of a shorter-EN-suffix entry.
  R2 — Too short: >=3 EN content words but <3 CJK chars;
                  >=4 EN content words but <4 CJK chars.
  R3 — Generic tail: multi-word EN whose ZH is a bare generic noun
       (法术/动作/效果/生物/物品/能力…).
  R4 — Fragment: ZH starts with a fragment prefix (之/其/此/其父/名为/例如/比如…)
       or ends with a dangling particle (中/等/啊/吧/呢 with 3+ chars).
  R5 — Stray English: ZH contains an English substring of 3+ letters (unless
       EN itself is an abbreviation we explicitly allow, e.g. `Cha/Dex/Int`).

A wiki replacement must itself pass R1..R5 or it's rejected.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

MAIN = Path(r"C:\Users\Taka\Desktop\fvtt\glossary.json")
WIKI = Path(__file__).resolve().parent / "out" / "glossary_wiki.json"
OUT_DIR = Path(__file__).resolve().parent / "out"

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EN_RUN_RE = re.compile(r"[A-Za-z]{3,}")

EN_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "by", "with", "from", "as", "is", "was", "be", "been",
}

# ZH strings we consider "generic tail" — safe noun on its own but a truncation
# when paired with a multi-word EN.
GENERIC_TAILS = {
    "能力", "动作", "效果", "地点", "生物", "术语", "法术", "技能", "状态",
    "物品", "符文", "武器", "护甲", "区域", "环境", "位置", "世界", "位面",
    "名字", "名称", "身份", "种类", "类型", "人物", "角色", "数据", "信息",
    "特征", "特性", "点数",
    "可能性", "结果", "选择", "方式", "方法", "过程", "时间", "空间",
    "伤害", "阵营", "学识", "元素", "族裔", "魔法", "语言", "召唤",
    "恶魔", "魔族", "怪物", "建筑", "气候", "动物", "植物", "神祇",
    "大师", "大迁徙", "仪式", "黑暗", "呼唤", "市长", "方向", "比赛",
    "毒素", "号子", "凉粉", "伯爵", "撞铁", "托尔",
}

FRAGMENT_PREFIXES = (
    "之", "其父", "其母", "其子", "其中", "其", "此", "该", "名为",
    "叫做", "名叫", "例如", "比如", "请", "对于", "关于", "至于",
    "由于", "以至", "因此", "所以",
)
FRAGMENT_END_PARTICLES = ("中", "等", "啊", "吧", "呀", "哟", "呢", "嘛", "了")

# EN sub-sequences allowed to appear inside ZH (attribute abbreviations etc.)
ALLOWED_EN_IN_ZH = {"Cha", "Dex", "Int", "Str", "Wis", "Con", "NPC", "HP", "DC", "AC", "GM"}

# R6 — role-noun templates. These ZH are fine for their canonical EN term,
# but wiki NPC templates captured them for hundreds of proper-name entries
# that lost the character name. Keys are the role-noun ZH; values are the
# set of lowercased EN strings considered legitimate for that ZH. Anything
# else mapping to that ZH is a template truncation -> delete.
ROLE_NOUN_CANONICAL: dict[str, set[str]] = {
    "业主": {"proprietor", "owner", "shopkeeper", "shop owner", "landlord"},
    "顾客": {"customer", "patron", "client", "buyer"},
    "教友": {"fellow worshipper", "fellow worshiper", "congregant", "worshipper", "worshiper", "faithful"},
    "住户": {"resident", "tenant", "occupant", "inhabitant"},
    "学生": {"student", "pupil", "apprentice", "students"},
    "高阶女祭司": {"high priestess"},
    "高阶祭祀": {"high priest"},
    "讲师": {"lecturer", "docent", "instructor", "teacher"},
    "主顾": {"patron", "client", "customer"},
    "观众": {"audience", "spectator", "viewer", "onlooker"},
    "山脉": {"mountain", "mountain range", "range", "mountains"},
    "本能能力": {"instinct ability"},
    "队长": {"captain", "leader", "chief"},
    "伙伴": {"companion", "partner", "companions", "partners", "ally", "allies"},
    "冒险": {"adventure", "adventuring"},
    "女王": {"queen"},
    "家族": {"family", "clan", "house"},
    "神术": {"divine spell", "divine magic", "divine", "divine spells"},
    "精灵": {"elf", "elves", "spirit", "sprite"},
    "罕见传承": {"rare heritage", "uncommon heritage"},
    "罕见族裔": {"rare ancestry", "uncommon ancestry"},
    "疾病": {"disease", "illness", "sickness"},
    "入门": {"initiation", "introduction", "primer"},
    "异能": {"ability", "power", "occult", "occult spell", "occult magic", "occult spells"},
    "衰弱": {"debilitation", "debility", "weakness"},
    "火焰": {"flame", "fire", "flames", "fires"},
    "奥术": {"arcane", "arcana", "arcane spell", "arcane magic", "arcane spells"},
    "联盟": {"alliance", "league", "union"},
    "契约": {"contract", "pact", "covenant"},
    "角斗士": {"gladiator"},
    "群岛": {"archipelago", "isles", "islands"},
    "探索行动": {"exploration activity"},
    "灵导械": {"spellheart"},
    "动物伙伴": {"animal companion"},
    "地区": {"region", "district", "area", "regions", "districts", "areas"},
    "武器特征": {"weapon trait"},
    "特征": {"trait", "traits"},
    "变体": {"archetype", "variant", "variants"},
    "背景": {"background", "backgrounds"},
    "工具包": {"toolkit", "tool kit", "repair toolkit", "kit"},
    "工具": {"tool", "tools"},
    "天使": {"angel", "angels", "angel (trait)"},
    "赋礼": {"gift", "gifts"},
    "狗头人": {"kobold", "kobolds"},
    "尖塔": {"spire", "minaret", "tower"},
    "氏族": {"clan", "clans"},
    "命运": {"fate", "the fates", "fates", "destiny"},
    "宝库": {"vault", "vaults", "the vault"},
    "神殿": {"temple", "temples", "shrine"},
    "大君": {"maharajah", "maharaja"},
    "城堡": {"castle", "keep", "fortress"},
    "指挥官": {"commander"},
    "恐惧": {"fear", "dread", "terror"},
    "秘密": {"secret", "secrets"},
    "起源": {"origin", "origins", "genesis"},
    "拖拽": {"drag", "pull"},
    "灵光": {"aura", "auras"},
    "语言": {"language", "languages", "tongue"},
    "位面": {"plane", "planes"},
    "重击": {"critical hit", "critical", "critical strike"},
    "思维空间": {"mindscape"},
    "怪物图鉴": {"bestiary", "monster manual"},
    "动作": {"action", "actions", "interaction", "reactions"},
}

# R7 — verb-prefix ZH (把/使/让/令/给). Often legitimate in compounds, so
# per-prefix allow list for the char that FOLLOWS the prefix. Any following
# char outside this list means it's a stray verb particle -> flag.
VERB_PREFIX_COMPOUND: dict[str, set[str]] = {
    "把": {"握", "戏", "柄", "手", "守", "持"},
    "使": {"节", "者", "用", "馆", "命", "徒", "团", "役", "唤", "劲"},
    "让": {"步", "位", "与", "给"},
    "令": {"人", "牌", "箭", "牌", "箭"},
    "给": {"予", "养"},
}


def en_content_tokens(en: str) -> list[str]:
    """Content words only: lowercase, stripped of leading/trailing punctuation,
    and excluding grammatical stopwords. `Thousands?` -> `thousands` (kept);
    `with`/`of` -> dropped. Parenthesized specifiers like `(TPK)` or `(trait)`
    are dropped so they don't inflate the token count."""
    stripped = re.sub(r"[（(][^）)]*[）)]?", " ", en)
    toks = [t for t in re.split(r"[ \-]", stripped.strip().lower()) if t]
    cleaned = [re.sub(r"^[^a-z]+|[^a-z]+$", "", t) for t in toks]
    return [t for t in cleaned if t and t not in EN_STOPWORDS and t.isalpha()]


def cjk_count(zh: str) -> int:
    return sum(1 for c in zh if CJK_RE.match(c))


def check_correspondence(
    en: str, zh: str, zh_by_en_lower: dict[str, str]
) -> str | None:
    """Return None if OK, else a short reason code for the failure."""
    if not zh or cjk_count(zh) == 0:
        return "R0_no_cjk"

    tokens = en_content_tokens(en)
    zc = cjk_count(zh)

    # R1 — likely truncation. Only fires when:
    #   * EN has 3+ content words
    #   * Some shorter EN-suffix exists in main with IDENTICAL ZH
    #   * ZH density is low (< 1.5 CJK chars per content word)
    #   * EN has no parens — "total party kill (TPK)" vs "TPK" both map to
    #     团灭 legitimately as synonym; paren-specifier is not a truncation.
    if len(tokens) >= 3 and "(" not in en and "（" not in en:
        for L in range(1, len(tokens)):
            suffix = " ".join(tokens[-L:])
            other = zh_by_en_lower.get(suffix)
            if other is not None and other == zh and zc < len(tokens) * 1.5:
                return "R1_truncated"

    # R2 — too short for EN word count. Idiomatic 2-char ZH can cover up to
    # 3-word EN (`holding your breath -> 屏息`, `total party kill -> 团灭`),
    # so we only flag at 4+ content words. Skip enumerations like
    # `d4, d6, d8, d10, d12, d20, and d100` where EN is literally a list.
    if "," in en and len(en.split(",")) >= 3:
        pass  # EN enumeration — ZH mirrors it, not a term translation
    elif len(tokens) >= 4 and zc < 3:
        return "R2_too_short"
    elif len(tokens) >= 6 and zc < 4:
        return "R2_too_short"

    # R3 — generic tail with 2+-word EN (only fires for tail nouns in the
    # deliberate stoplist like 法术/动作/伤害/元素 etc.)
    if len(tokens) >= 2 and zh in GENERIC_TAILS:
        return "R3_generic_tail"

    # R4 — fragment prefix (`之`, `其`, `由` as sentence starter).
    # Trailing-particle checks removed — 吧/等/了/中 all appear in legitimate
    # compound words (酒吧/等级/少不了/环境中), so the rule mislabeled them.
    if zh.startswith(FRAGMENT_PREFIXES):
        return "R4_fragment_prefix"

    # R5 — stray English inside ZH (not in allow-list)
    for m in EN_RUN_RE.finditer(zh):
        if m.group() not in ALLOWED_EN_IN_ZH:
            return "R5_stray_english"

    # R6 — role-noun truncation. ZH is a known wiki-template role noun, and
    # this EN is not the canonical term for it (so the EN's proper-name
    # modifier was dropped).
    if zh in ROLE_NOUN_CANONICAL:
        if en.lower().strip() not in ROLE_NOUN_CANONICAL[zh]:
            return "R6_role_truncation"

    # R7 — verb-prefix ZH (把/使/让/令/给) where the following char is not
    # part of an allowed compound. Restricted to single-token EN to avoid
    # killing legitimate sentence-level translations like `Let the Flesh
    # Fester -> 让肉烂一会儿` or `Induce Awe -> 让人敬畏`.
    if len(tokens) <= 1 and len(zh) >= 2 and zh[0] in VERB_PREFIX_COMPOUND:
        if zh[1] not in VERB_PREFIX_COMPOUND[zh[0]]:
            return "R7_verb_prefix"

    return None


def lookup_wiki_replacement(
    en: str,
    current_zh: str,
    wiki: dict[str, dict],
    zh_by_en_lower: dict[str, str],
) -> str | None:
    """Find a wiki ZH candidate that (a) passes correspondence, (b) has
    strictly more CJK coverage than the current ZH, and (c) has meaningful
    data-source support (count >= 2). Returns None otherwise."""
    data = wiki.get(en)
    if data is None:
        low = en.lower()
        for k, v in wiki.items():
            if k.lower() == low:
                data = v
                break
    if data is None:
        return None

    cands: list[tuple[str, int]] = [(data["zh"], data["count"])]
    for alt_zh, alt_count in (data.get("alternatives") or {}).items():
        cands.append((alt_zh, alt_count))
    cands.sort(key=lambda c: -c[1])

    current_len = cjk_count(current_zh)
    for zh, count in cands:
        if not isinstance(zh, str) or not zh:
            continue
        if count < 2:
            continue
        if cjk_count(zh) <= current_len:
            continue
        if check_correspondence(en, zh, zh_by_en_lower) is None:
            return zh
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report only, do not modify the file")
    ap.add_argument("--no-replace", action="store_true", help="Only delete on mismatch; never swap in wiki candidate")
    args = ap.parse_args(argv)

    g = json.loads(MAIN.read_text(encoding="utf-8"))
    wiki = json.loads(WIKI.read_text(encoding="utf-8"))
    before = len(g)

    # zh_by_en_lower: lookup for R1 (only string values)
    zh_by_en_lower: dict[str, str] = {}
    for k, v in g.items():
        if isinstance(v, str):
            zh_by_en_lower[k.lower()] = v

    stats: dict[str, int] = defaultdict(int)
    samples: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # reason -> [(en, before, after)]
    to_delete: list[str] = []
    to_replace: list[tuple[str, str, str]] = []  # (en, old, new)

    for en, v in list(g.items()):
        if isinstance(v, list):
            stats["kept_list"] += 1
            continue
        if not isinstance(v, str):
            stats["kept_other"] += 1
            continue
        reason = check_correspondence(en, v, zh_by_en_lower)
        if reason is None:
            stats["kept_ok"] += 1
            continue

        # Try to replace from wiki
        repl = None if args.no_replace else lookup_wiki_replacement(en, v, wiki, zh_by_en_lower)
        if repl is not None and repl != v:
            to_replace.append((en, v, repl))
            stats[f"replaced_{reason}"] += 1
            if len(samples[reason]) < 20:
                samples[reason].append((en, v, repl))
        else:
            to_delete.append(en)
            stats[f"deleted_{reason}"] += 1
            if len(samples[reason]) < 20:
                samples[reason].append((en, v, "<DELETE>"))

    # Apply changes
    if not args.dry_run:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = MAIN.with_suffix(f".json.bak.{ts}")
        shutil.copy2(MAIN, backup)
        for en, _old, new in to_replace:
            g[en] = new
        for en in to_delete:
            g.pop(en, None)
        MAIN.write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Backup: {backup.name}")
        print(f"Glossary: {before} -> {len(g)} entries")
    else:
        print(f"(dry-run) Would delete {len(to_delete)}, replace {len(to_replace)}")
        print(f"Net: {before} -> {before - len(to_delete)} entries")

    # Report
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = OUT_DIR / f"verify_report_{ts}.md"
    lines = [
        "# Correspondence verification report",
        f"Run: {ts}",
        f"Target: `{MAIN}`",
        f"Wiki source: `{WIKI.name}` ({len(wiki)} entries)",
        "",
        "## Stats",
        "",
    ]
    for k, v in sorted(stats.items()):
        lines.append(f"- `{k}`: {v}")

    for reason, entries in sorted(samples.items()):
        lines += ["", f"## {reason} samples (first {len(entries)})", "", "| EN | before | after |", "|---|---|---|"]
        for en, old, new in entries:
            lines.append(f"| `{en}` | {old!r} | {new!r} |")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report}")

    print("\nStats:")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
