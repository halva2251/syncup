"""
Embedding validation: does all-MiniLM-L6-v2 produce cross-domain taste clusters?

We embed ~35 items per service (Steam, Spotify/music, AniList/anime) spanning
a deliberate range of vibes. Then UMAP to 2D. If the model captures taste rather
than just service-type, items with similar aesthetics should cluster regardless
of which platform they came from.

Hypothesis: dark/atmospheric/melancholic items across services will cluster
together; upbeat/action items will form their own neighbourhood.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import numpy as np
import umap
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Item corpus — deliberately broad and varied within each service
# Labels encode the expected aesthetic cluster for visual verification
# ---------------------------------------------------------------------------

ITEMS: list[dict] = [
    # ── STEAM GAMES ─────────────────────────────────────────────────────────
    # dark/atmospheric
    {
        "text": "Disco Elysium: A story-rich RPG set in a crumbling city. Existential, melancholic, politically charged. A detective piece about failure and ideology.",
        "service": "steam",
        "vibe": "dark-literary",
    },
    {
        "text": "Hollow Knight: Dark atmospheric metroidvania set in a vast underground insect kingdom. Silent, melancholic, beautifully desolate.",
        "service": "steam",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Bloodborne: Gothic horror action RPG. Dark Souls-style combat in a nightmarish Victorian city consumed by eldritch cosmic horror.",
        "service": "steam",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Darkest Dungeon: Gothic horror roguelike about managing stress and sanity while exploring cursed dungeons. Brutal and oppressive.",
        "service": "steam",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Pathologic 2: A brutal survival game about a doctor trying to stop a plague in a strange dying town. Kafka-esque dread and existential weight.",
        "service": "steam",
        "vibe": "dark-literary",
    },
    {
        "text": "Outer Wilds: A mystery game about exploring a solar system stuck in a 22-minute time loop. Melancholic wonder, existential scale.",
        "service": "steam",
        "vibe": "melancholic-wonder",
    },
    {
        "text": "What Remains of Edith Finch: A walking sim exploring a cursed family's stories through their abandoned house. Beautiful and quietly devastating.",
        "service": "steam",
        "vibe": "melancholic-wonder",
    },
    # upbeat/action/competitive
    {
        "text": "Rocket League: Competitive vehicular soccer. Fast-paced skill-based gameplay, team coordination, e-sports scene.",
        "service": "steam",
        "vibe": "competitive-energetic",
    },
    {
        "text": "Counter-Strike 2: Competitive tactical first-person shooter. Precise gunplay, team economy, map control.",
        "service": "steam",
        "vibe": "competitive-energetic",
    },
    {
        "text": "Hades: Fast-paced roguelike dungeon crawler with tight action combat. Bright mythology aesthetic, excellent narrative.",
        "service": "steam",
        "vibe": "upbeat-action",
    },
    {
        "text": "Deep Rock Galactic: Co-op first-person shooter where space dwarves mine caves and kill bugs. Extremely fun, team-oriented, joyful.",
        "service": "steam",
        "vibe": "upbeat-action",
    },
    {
        "text": "Stardew Valley: Relaxing farming simulation. Build a farm, befriend villagers, fish, mine. Cozy and wholesome.",
        "service": "steam",
        "vibe": "cozy-wholesome",
    },
    {
        "text": "Animal Crossing New Horizons: Life simulation on a deserted island. Cozy, relaxing, community-focused.",
        "service": "steam",
        "vibe": "cozy-wholesome",
    },
    # cinematic narrative
    {
        "text": "The Last of Us Part II: Story-driven survival game about revenge and trauma in a post-apocalyptic world. Emotionally brutal and cinematic.",
        "service": "steam",
        "vibe": "cinematic-emotional",
    },
    {
        "text": "Red Dead Redemption 2: Open-world Western epic about an outlaw in a dying era. Slow, cinematic, profound narrative about masculinity and mortality.",
        "service": "steam",
        "vibe": "cinematic-emotional",
    },
    {
        "text": "Death Stranding: A contemplative walking game about reconnecting a fractured America. Slow, philosophical, divisive. Kojima at his most ambitious.",
        "service": "steam",
        "vibe": "dark-literary",
    },
    # horror
    {
        "text": "Resident Evil Village: First-person survival horror. Gothic castle, tense atmosphere, iconic villain Lady Dimitrescu.",
        "service": "steam",
        "vibe": "horror",
    },
    {
        "text": "Alien Isolation: First-person survival horror aboard a space station. Extremely tense, slow-burn dread. The xenomorph cannot be killed.",
        "service": "steam",
        "vibe": "horror",
    },
    # ── MUSIC ────────────────────────────────────────────────────────────────
    # dark/atmospheric electronic
    {
        "text": "Burial — Untrue: Hauntological UK garage and dubstep. Grainy, melancholic, ghostly. Urban loneliness crystallised in sound.",
        "service": "music",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Grouper — Ruins: Hazy lo-fi folk. Piano and voice through reverb. Intensely introspective and isolationist.",
        "service": "music",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "The Caretaker — Everywhere at the End of Time: Decaying ballroom music representing dementia. Harrowing, beautiful, devastating art piece.",
        "service": "music",
        "vibe": "dark-literary",
    },
    {
        "text": "Boards of Canada — Music Has the Right to Children: Warm hazy IDM electronica. Childhood nostalgia filtered through something slightly wrong.",
        "service": "music",
        "vibe": "melancholic-wonder",
    },
    {
        "text": "Mount Eerie — A Crow Looked at Me: Sparse folk-rock about grief after his wife's death from cancer. Devastatingly direct and literary.",
        "service": "music",
        "vibe": "dark-literary",
    },
    {
        "text": "Portishead — Dummy: Trip-hop. Cinematic, dark, sensual. Orchestral samples over scratchy beats. Beth Gibbons' haunted voice.",
        "service": "music",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Radiohead — OK Computer: Art rock. Alienation and paranoia in the late 90s. Angular guitars, Thom Yorke's falsetto, dystopian dread.",
        "service": "music",
        "vibe": "dark-literary",
    },
    # upbeat/energetic
    {
        "text": "Daft Punk — Random Access Memories: Disco-influenced electronic dance music. Euphoric, nostalgic, lush production. Get Lucky, Instant Crush.",
        "service": "music",
        "vibe": "upbeat-action",
    },
    {
        "text": "Kendrick Lamar — DAMN.: Hip-hop. Dense lyricism, complex themes of race, religion, Compton. Aggressive and virtuosic.",
        "service": "music",
        "vibe": "competitive-energetic",
    },
    {
        "text": "Charli XCX — brat: PC music-influenced hyperpop. Hedonistic, chaotic, maximalist club music for the anxious generation.",
        "service": "music",
        "vibe": "competitive-energetic",
    },
    {
        "text": "Tyler the Creator — IGOR: Neo-soul and hip-hop. A heartbreak concept album with lush orchestration and fractured emotion.",
        "service": "music",
        "vibe": "cinematic-emotional",
    },
    # cozy/wholesome
    {
        "text": "Norah Jones — Come Away with Me: Soft jazz-folk. Warm, intimate, acoustic. Perfect for late autumn evenings.",
        "service": "music",
        "vibe": "cozy-wholesome",
    },
    {
        "text": "Fleet Foxes — Helplessness Blues: Indie folk. Rich harmonies, pastoral imagery, searching for meaning in a modern world.",
        "service": "music",
        "vibe": "melancholic-wonder",
    },
    # cinematic
    {
        "text": "Hans Zimmer — Interstellar OST: Epic orchestral film score. Pipe organ and strings evoking cosmic scale and emotional enormity.",
        "service": "music",
        "vibe": "melancholic-wonder",
    },
    {
        "text": "Ennio Morricone — The Good the Bad and the Ugly OST: Spaghetti western film score. Iconic, dusty, cinematic tension.",
        "service": "music",
        "vibe": "cinematic-emotional",
    },
    # horror
    {
        "text": "Health — Death Magic: Industrial noise-rock. Abrasive, claustrophobic, relentless. A sonic panic attack.",
        "service": "music",
        "vibe": "horror",
    },
    {
        "text": "Swans — The Seer: Post-rock/noise. Maximalist, ritualistic, overwhelming. 2 hours of confrontational intensity.",
        "service": "music",
        "vibe": "horror",
    },
    # ── ANIME / FILM ─────────────────────────────────────────────────────────
    # dark/atmospheric
    {
        "text": "Neon Genesis Evangelion: Psychological mecha anime. Depression, identity crisis, and world-ending stakes through the lens of a traumatised teenager.",
        "service": "anime",
        "vibe": "dark-literary",
    },
    {
        "text": "Serial Experiments Lain: Cyberpunk psychological anime. Identity, the internet, and reality dissolving. Dense, cryptic, haunting.",
        "service": "anime",
        "vibe": "dark-literary",
    },
    {
        "text": "Texhnolyze: Dystopian cyberpunk anime set in an underground dying city. Nihilistic, violent, slow-burn existential horror.",
        "service": "anime",
        "vibe": "dark-atmospheric",
    },
    {
        "text": "Paranoia Agent: Satoshi Kon psychological thriller anime about a shared mass hysteria in Tokyo. Surreal, unsettling, socially critical.",
        "service": "anime",
        "vibe": "dark-literary",
    },
    {
        "text": "Made in Abyss: Adventure anime about children descending into a vast cursed abyss. Begins beautiful and whimsical, becomes brutal and disturbing.",
        "service": "anime",
        "vibe": "dark-atmospheric",
    },
    # melancholic wonder
    {
        "text": "Spirited Away: Miyazaki fantasy. A girl navigating a spirit world to save her parents. Wonder, warmth, and a deep undercurrent of melancholy.",
        "service": "anime",
        "vibe": "melancholic-wonder",
    },
    {
        "text": "Your Name: Romantic fantasy about two teenagers swapping bodies across time. Visually stunning, emotionally devastating.",
        "service": "anime",
        "vibe": "cinematic-emotional",
    },
    {
        "text": "A Silent Voice: Coming-of-age anime about bullying, deafness, guilt, and redemption. Quietly devastating.",
        "service": "anime",
        "vibe": "cinematic-emotional",
    },
    {
        "text": "Violet Evergarden: Post-war anime about an emotionally numbed soldier learning to understand human feelings. Gorgeous and melancholic.",
        "service": "anime",
        "vibe": "melancholic-wonder",
    },
    # upbeat/action
    {
        "text": "Attack on Titan: Dark action anime. Humanity surviving inside walls against giant human-eating creatures. Intense, morally complex, epic.",
        "service": "anime",
        "vibe": "upbeat-action",
    },
    {
        "text": "Demon Slayer: Action shounen anime with stunning animation. A boy trains to become a demon slayer to avenge his family.",
        "service": "anime",
        "vibe": "upbeat-action",
    },
    {
        "text": "Haikyuu: Sports anime about competitive high school volleyball. Extremely energetic, team dynamics, pure adrenaline.",
        "service": "anime",
        "vibe": "competitive-energetic",
    },
    # cozy
    {
        "text": "Yotsuba: Slice-of-life manga about a small quirky girl experiencing everyday life with wonder. Warm, gentle, joyful.",
        "service": "anime",
        "vibe": "cozy-wholesome",
    },
    {
        "text": "Mushishi: Supernatural anthology about a traveller encountering mysterious life-forms. Slow, contemplative, quietly magical.",
        "service": "anime",
        "vibe": "melancholic-wonder",
    },
    # horror
    {
        "text": "Berserk: Dark fantasy manga/anime. A mercenary's descent through medieval horror, trauma, and betrayal. Brutal and uncompromising.",
        "service": "anime",
        "vibe": "horror",
    },
    {
        "text": "Junji Ito Collection: Horror anthology anime based on Ito's manga. Body horror, cosmic dread, mundane situations turned nightmarish.",
        "service": "anime",
        "vibe": "horror",
    },
]

# ---------------------------------------------------------------------------
# Embed
# ---------------------------------------------------------------------------


def main() -> None:
    out_dir = Path(__file__).parent
    print("Loading model all-MiniLM-L6-v2...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [item["text"] for item in ITEMS]
    services = [item["service"] for item in ITEMS]
    vibes = [item["vibe"] for item in ITEMS]
    labels = [item["text"].split(":")[0] for item in ITEMS]

    print(f"Embedding {len(texts)} items...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    print(f"Embedding shape: {embeddings.shape}")

    # ---------------------------------------------------------------------------
    # UMAP reduction
    # ---------------------------------------------------------------------------
    print("Running UMAP...")
    reducer = umap.UMAP(
        n_components=2, n_neighbors=12, min_dist=0.15, random_state=42, metric="cosine"
    )
    coords = reducer.fit_transform(embeddings)

    # ---------------------------------------------------------------------------
    # Plot 1: Coloured by SERVICE — the key test
    # If this shows tight service-only blobs with no mixing, embeddings don't
    # capture cross-domain taste. If vibes cross service boundaries, we're good.
    # ---------------------------------------------------------------------------
    service_colors = {"steam": "#ef4444", "music": "#22c55e", "anime": "#3b82f6"}
    service_markers = {"steam": "o", "music": "s", "anime": "^"}

    fig, axes = plt.subplots(1, 2, figsize=(20, 9))
    fig.suptitle(
        "SyncUp Embedding Validation — all-MiniLM-L6-v2", fontsize=15, fontweight="bold", y=1.01
    )

    ax1 = axes[0]
    ax1.set_title("Coloured by SERVICE\n(blobs = bad, mixing = good)", fontsize=12)
    for service, color in service_colors.items():
        mask = [s == service for s in services]
        idxs = [i for i, m in enumerate(mask) if m]
        ax1.scatter(
            coords[idxs, 0],
            coords[idxs, 1],
            c=color,
            marker=service_markers[service],
            s=80,
            alpha=0.85,
            edgecolors="white",
            linewidth=0.5,
            label=service,
        )
    for i, label in enumerate(labels):
        ax1.annotate(
            label,
            (coords[i, 0], coords[i, 1]),
            fontsize=5.5,
            alpha=0.65,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax1.legend(fontsize=10)
    ax1.set_xlabel("UMAP-1")
    ax1.set_ylabel("UMAP-2")
    ax1.grid(True, alpha=0.15)

    # ---------------------------------------------------------------------------
    # Plot 2: Coloured by VIBE — expected aesthetic clusters
    # This shows what the model actually learned to group together.
    # ---------------------------------------------------------------------------
    vibe_colors = {
        "dark-literary": "#7c3aed",
        "dark-atmospheric": "#1e1b4b",
        "melancholic-wonder": "#0891b2",
        "cinematic-emotional": "#ea580c",
        "upbeat-action": "#16a34a",
        "competitive-energetic": "#ca8a04",
        "cozy-wholesome": "#db2777",
        "horror": "#991b1b",
    }
    unique_vibes = list(vibe_colors.keys())

    ax2 = axes[1]
    ax2.set_title("Coloured by VIBE CLUSTER\n(expected aesthetic groupings)", fontsize=12)
    for vibe in unique_vibes:
        mask = [v == vibe for v in vibes]
        idxs = [i for i, m in enumerate(mask) if m]
        if not idxs:
            continue
        ax2.scatter(
            coords[idxs, 0],
            coords[idxs, 1],
            c=vibe_colors[vibe],
            marker="o",
            s=80,
            alpha=0.85,
            edgecolors="white",
            linewidth=0.5,
            label=vibe,
        )
    for i, label in enumerate(labels):
        ax2.annotate(
            label,
            (coords[i, 0], coords[i, 1]),
            fontsize=5.5,
            alpha=0.65,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_xlabel("UMAP-1")
    ax2.set_ylabel("UMAP-2")
    ax2.grid(True, alpha=0.15)

    plt.tight_layout()
    out_path = out_dir / "embedding_validation.png"
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"\nSaved → {out_path}")

    # ---------------------------------------------------------------------------
    # Quantitative: cosine similarity between known cross-domain vibe pairs
    # ---------------------------------------------------------------------------
    print("\n── Cross-domain similarity spot-checks ──")
    spot_checks = [
        ("Hollow Knight", "Burial — Untrue", "expected HIGH (both dark atmospheric)"),
        ("Disco Elysium", "Radiohead — OK Computer", "expected HIGH (both dark-literary)"),
        (
            "Pathologic 2",
            "The Caretaker — Everywhere at the End of Time",
            "expected HIGH (literary dread)",
        ),
        ("Bloodborne", "Junji Ito Collection", "expected HIGH (both horror)"),
        (
            "Outer Wilds",
            "Boards of Canada — Music Has the Right to Children",
            "expected HIGH (melancholic wonder)",
        ),
        ("Hades", "Daft Punk — Random Access Memories", "expected MED-HIGH (upbeat energetic)"),
        ("Stardew Valley", "Norah Jones — Come Away with Me", "expected MED (cozy wholesome)"),
        ("Rocket League", "Burial — Untrue", "expected LOW (very different vibes)"),
        ("Disco Elysium", "Daft Punk — Random Access Memories", "expected LOW (opposite ends)"),
    ]

    label_to_idx = {item["text"].split(":")[0]: i for i, item in enumerate(ITEMS)}
    results = []
    for a, b, note in spot_checks:
        if a in label_to_idx and b in label_to_idx:
            ia, ib = label_to_idx[a], label_to_idx[b]
            sim = float(np.dot(embeddings[ia], embeddings[ib]))
            print(f"  {sim:.3f}  {a}  ×  {b}  [{note}]")
            results.append((sim, a, b, note))

    # Compute average cross-domain same-vibe similarity vs different-vibe
    same_vibe_sims, diff_vibe_sims = [], []
    for i in range(len(ITEMS)):
        for j in range(i + 1, len(ITEMS)):
            if services[i] != services[j]:  # cross-domain only
                sim = float(np.dot(embeddings[i], embeddings[j]))
                if vibes[i] == vibes[j]:
                    same_vibe_sims.append(sim)
                else:
                    diff_vibe_sims.append(sim)

    print("\n── Cross-domain similarity averages ──")
    print(
        f"  Same vibe, different service:  {np.mean(same_vibe_sims):.3f} (n={len(same_vibe_sims)})"
    )
    print(
        f"  Diff vibe, different service:  {np.mean(diff_vibe_sims):.3f} (n={len(diff_vibe_sims)})"
    )
    delta = np.mean(same_vibe_sims) - np.mean(diff_vibe_sims)
    print(f"  Delta (signal strength):       {delta:.3f}")
    if delta > 0.03:
        print("  ✅ POSITIVE SIGNAL — cross-domain vibe clustering detected")
    elif delta > 0.01:
        print("  ⚠️  WEAK SIGNAL — marginal cross-domain clustering")
    else:
        print("  ❌ NO SIGNAL — embeddings don't separate vibes across domains")

    print(f"\nDone. View: {out_path}")


if __name__ == "__main__":
    main()
