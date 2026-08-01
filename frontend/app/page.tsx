/*
THESIS: SyncUp is introduced through the idea of a whole taste profile, not through a generic SaaS hero or an illustrative app mockup.
OWN-WORLD: Quiet neutral surfaces, restrained electric blue, fine rules, DM Sans at editorial scale, and a monochrome moving service strip.
STORY: Understand the project in one clear statement, then read how the matching pipeline and build fit together.
FIRST VIEWPORT: A compact header sits above a single wide text composition; access links remain visible at the top-right.
FORM: Text-led project introduction, derived from the project specimen structure. Surface seed 329f8d0e.
*/

import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Braces,
  Database,
  Fingerprint,
  GitCompareArrows,
  Sparkles,
  UsersRound,
} from "lucide-react";
import {
  siAnilist,
  siLastdotfm,
  siLetterboxd,
  siMusicbrainz,
  siReddit,
  siSpotify,
  siSteam,
  siTrakt,
} from "simple-icons";
import { AppIcon } from "@/components/ui/app-icon";
import styles from "./homepage.module.css";

const sources = [
  { name: "Spotify", brand: siSpotify },
  { name: "Steam", brand: siSteam },
  { name: "Letterboxd", brand: siLetterboxd },
  { name: "AniList", brand: siAnilist },
  { name: "Last.fm", brand: siLastdotfm },
  { name: "Trakt", brand: siTrakt },
  { name: "Reddit", brand: siReddit },
  { name: "RateYourMusic", brand: siMusicbrainz },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label="SyncUp home">
      <AppIcon icon={Sparkles} size="xs" gradient="brand" />
      <span className="text-[17px] font-bold tracking-[-0.02em]">SyncUp</span>
    </Link>
  );
}

export default function IndexPage() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Brand />

          <nav className={styles.mainNav} aria-label="Homepage">
            <Link href="#project">Project</Link>
            <Link href="#method">Method</Link>
            <Link href="#build">Build</Link>
          </nav>

          <nav className={styles.accountNav} aria-label="Account">
            <Link href="/login" className={styles.loginLink}>
              Log in
            </Link>
            <Link href="/signup" className={styles.registerLink}>
              Register
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </nav>
        </div>
      </header>

      <section className={styles.hero} id="project">
        <div className={styles.heroCopy}>
          <h1>
            Your taste has a shape.
            <span>SyncUp compares the whole thing.</span>
          </h1>
          <p>
            A cross-domain matching project that turns what you play, watch,
            listen to, rate, and follow into one taste profile—then looks for
            people on a similar wavelength.
          </p>
          <div className={styles.heroLinks}>
            <Link href="#method" className={styles.textLink}>
              See how it works
              <ArrowDown size={17} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section className={styles.serviceTicker} aria-label="Connected services">
        <div className={styles.tickerViewport}>
          <div className={styles.tickerTrack}>
            {[0, 1].map((group) => (
              <div className={styles.tickerGroup} key={group} aria-hidden={group === 1}>
                {sources.map((source) => (
                  <div className={styles.tickerService} key={`${group}-${source.name}`}>
                    <svg
                      className={styles.tickerIcon}
                      viewBox="0 0 24 24"
                      role="img"
                      aria-label={source.name}
                    >
                      <path d={source.brand.path} />
                    </svg>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.methodSection} id="method">
        <div className={styles.sectionIntro}>
          <h2>Not a quiz. A pipeline you can inspect.</h2>
          <p>
            SyncUp starts with the trail your accounts already contain. The
            system brings that activity into a shared semantic space without
            pretending every click says the same thing.
          </p>
        </div>

        <div className={styles.pipeline}>
          <div className={styles.pipelineStep}>
            <div className={styles.pipelineIcon}>
              <Database size={21} aria-hidden="true" />
            </div>
            <div>
              <span>Bring in the trail</span>
              <h3>Libraries, ratings, playtime, repeats, communities.</h3>
              <p>
                Eight service connectors normalize very different kinds of
                activity into a consistent item history.
              </p>
            </div>
            <span className={styles.stepMeta}>SYNC</span>
          </div>

          <div className={styles.pipelineStep}>
            <div className={styles.pipelineIcon}>
              <Braces size={21} aria-hidden="true" />
            </div>
            <div>
              <span>Translate the context</span>
              <h3>Each item becomes more than a title string.</h3>
              <p>
                Genre, format, engagement, and available metadata are
                serialized into semantic embeddings, then aggregated into a
                weighted profile.
              </p>
            </div>
            <span className={styles.stepMeta}>384D</span>
          </div>

          <div className={styles.pipelineStep}>
            <div className={styles.pipelineIcon}>
              <GitCompareArrows size={21} aria-hidden="true" />
            </div>
            <div>
              <span>Compare the signal</span>
              <h3>Shared taste with the overlap made visible.</h3>
              <p>
                The current matcher rarity-weights shared items, then shows a
                compatibility score with per-service breakdowns and concrete
                highlights.
              </p>
            </div>
            <span className={styles.stepMeta}>MATCH</span>
          </div>
        </div>
      </section>

      <section className={styles.buildSection} id="build">
        <div className={styles.buildTopline}>
          <h2>Under the hood.</h2>
        </div>

        <div className={styles.buildGrid}>
          <article className={styles.buildPrimary}>
            <div className={styles.buildIcon}>
              <Fingerprint size={30} aria-hidden="true" />
            </div>
            <div>
              <span>Semantic layer</span>
              <h3>A common space for very different taste.</h3>
              <p>
                Sentence-transformer embeddings turn enriched items into
                comparable vectors. User profiles are aggregated with
                engagement and user-controlled weighting.
              </p>
            </div>
          </article>

          <article className={styles.buildSide}>
            <UsersRound size={25} aria-hidden="true" />
            <div>
              <span>Experience layer</span>
              <h3>Profiles, matches, and things to explore next.</h3>
              <p>
                A Next.js interface for onboarding, profile control,
                compatibility detail, and cross-domain recommendations.
              </p>
            </div>
          </article>

          <article className={styles.buildSide}>
            <Database size={25} aria-hidden="true" />
            <div>
              <span>Data layer</span>
              <h3>FastAPI, PostgreSQL, pgvector, and eight connectors.</h3>
              <p>
                OAuth and imports feed normalized histories into encrypted,
                session-based infrastructure with background sync jobs.
              </p>
            </div>
          </article>
        </div>
      </section>

      <footer className={styles.footer}>
        <Brand />
        <p className={styles.footerByline}>
          Project by{" "}
          <Link href="https://ruu.by" target="_blank" rel="noreferrer">
            Florian Ruby
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>{" "}
          &amp;{" "}
          <Link href="https://www.yensauliak.com/" target="_blank" rel="noreferrer">
            Yen Sauliak
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        </p>
      </footer>
    </main>
  );
}
