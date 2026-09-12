/**
 * Fixed, blurred colour fields behind every translucent panel in the app.
 * Purely decorative — aria-hidden, pointer-events-none, and its animation
 * is disabled under prefers-reduced-motion (see globals.css). Rendered once
 * in the root layout so it sits behind both the dashboard shell and the
 * auth pages without either needing to know about it.
 */
export default function BackgroundBlobs() {
  return (
    <div className="blob-field" aria-hidden="true">
      <div className="blob top-[-10%] left-[-5%] h-[26rem] w-[26rem] bg-indigo-400 animate-blob dark:bg-indigo-600" />
      <div className="blob top-[-5%] right-[-10%] h-[30rem] w-[30rem] bg-violet-400 animate-blob-slow dark:bg-violet-600" />
      <div className="blob bottom-[-15%] left-[20%] h-[24rem] w-[24rem] bg-cyan-300 animate-blob dark:bg-cyan-600" />
    </div>
  );
}
