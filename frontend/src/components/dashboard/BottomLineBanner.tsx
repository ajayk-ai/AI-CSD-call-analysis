import './BottomLineBanner.css';

interface BottomLineBannerProps {
  text: string;
}

export function BottomLineBanner({ text }: BottomLineBannerProps) {
  return (
    <section className="bottom-line">
      <div className="bottom-line__heading">
        <span className="bottom-line__icon">🧭</span>
        <span>Bottom Line</span>
      </div>
      <p className="bottom-line__text">{text}</p>
      <span className="bottom-line__trend">📈</span>
    </section>
  );
}
