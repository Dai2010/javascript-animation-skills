---
name: compose-music
description: Compose original music from a brief — chord progressions, voicings, melody, texture, form — then render it to WAV/MP3 with MIDI + fluidsynth. Use when the user asks to 作曲 / 写一段旋律 / 配和声 / 写和弦进行 / 编一段钢琴或乐队 / "make me a short piece", or asks how chords and progressions work. For transcribing an existing score use score-to-audio; for scoring an animation with code-synthesised audio use soundtrack.
---

# Compose

原创作曲。乐理口径取自李重光《基本乐理通用教材》（本机 `~/music/theory/leli_raw.txt`）。

**索引（只读你需要的那个文件）**

| 原理 | 一句话 | 文件 |
|---|---|---|
| 音程与协和度 | 数半音定名称；三度定色彩，七度定张力 | `references/intervals.md` |
| 三/七和弦与转位 | 大三 0-4-7、小三 0-3-7、属七 0-4-7-10；转位改低音不改根音 | `references/chords.md` |
| 调、调号、调式 | 五度循环定升降号；和声小调升七级；五声去掉 4、7 级 | `references/keys-modes.md` |
| 调内和弦与功能 | 正三和弦 I IV V = T S D；副三和弦做替代 | `references/functions.md` |
| 和声进行与终止 | T→S→D→T；句末必给终止，V–I 最硬 | `references/progressions.md` |
| 转调与离调 | 近关系用共同和弦；离调只借两小节 | `references/modulation.md` |
| 节奏与节拍 | 强拍放和弦根音/骨干音，切分靠跨拍时值 | `references/rhythm.md` |
| 旋律写法 | 动机 1 小节 → 乐句 4 → 乐段 8；重复加变化 | `references/melody.md` |
| 织体与声部 | 柱式/阿尔贝蒂/分解/band；低音区别堆密集和弦 | `references/texture.md` |
| 曲式 | 一段、两段（AB）、三段（ABA） | `references/form.md` |

## 流程

1. **定框架**：调、速度、拍号、小节数、曲式。默认 16 小节、4/4、♩=76。
2. **写级数谱**：先用罗马数字（`I V vi IV`）定功能，再落成具体和弦（可用借用和弦 `bVI bVII`、副属 `V/V`）。
3. **配声部**：`harmony.py` 做最近声部连接，别手算转位。
4. **写旋律**：强拍落和弦音，弱拍走经过/辅助音，句末长音。
5. **出 MIDI**：写 brief JSON → `compose.py`。
6. **渲染+校验**：`render.sh`，看输出的小节拍数、音域、`volumedetect`。

```sh
python3 scripts/harmony.py "Cmaj7 Am7 Dm7 G7" --key C          # 看 voicing
python3 scripts/harmony.py "ii7 V7 Imaj7" --key C --roman      # 级数 → 和弦
python3 scripts/compose.py examples/demo-brief.json -o out.mid
bash scripts/render.sh out.mid out.mp3                          # SOUNDFONT=... 可覆盖
```

## brief JSON

```json
{"title":"…","key":"C","mode":"major","tempo":76,"meter":4,
 "texture":"block|alberti|arpeggio|band","voices":4,"bars_per_chord":1,
 "chart":["Cmaj7","G/B","Am7","Fmaj7"],
 "melody":[{"bar":1,"beat":1,"dur":1,"note":"E5","vel":86}]}
```

`chart` 里写 `roman: true` 时可直接写 `I V vi IV` / `ii7 V7 Imaj7`；`bar`、`beat` 从 1 开始，`dur` 以四分音符为 1。

## 硬规则（违反就不是“写法问题”，是错）

- 相邻和弦的外声部禁平行五度、平行八度。
- 属七的七音下行级进解决，导音上行到主音；导七同理。
- 旋律与内声部避免低音区小二度/小九度撞音；跳进后反向级进。
- 低音区（<C3）不堆三度密集和弦，用八度、五度、开放排列。
- 句末必须终止：前句半终止（停 V），后句完全终止（V–I，旋律落主音）。
- 一个乐段 8 小节，动机 1 小节；超了就是两段。

## 校验与边界

- `compose.py` 会打印每轨音符数、发声拍数、音域、和弦序列；`bass` 的 sound-beats 必须等于 `bars × meter`。
- 成品必须 `volumedetect`：均值约 −17 dB、峰值 ≤ −1.5 dB（`alimiter=…:level=false`，`level` 开着会把峰值抬回 0 dB）。
- **我听不到成品**：我只能量电平和结构，好不好听由耳朵定；先给 20–30 秒试听。
- 规则生成不是灵感：`compose.py` 只保证和声、声部、节拍正确，旋律的“好听”仍要人改。
- SoundFont 决定音色上限（GeneralUser GS 比 MS Basic 高约 7 dB，也更像真钢琴）；没有人声、没有真实弦乐群。
