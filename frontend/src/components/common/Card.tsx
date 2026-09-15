import type { ReactNode } from 'react';
import { InfoTip } from './InfoTip';
import './Card.css';

export type CardVariant = 'panel' | 'red' | 'blue' | 'teal';

interface CardProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  /** Explanation shown on hover next to the title, for a metric that isn't
   *  self-evident to a first-time reader (e.g. what "Usable Calls" excludes). */
  tooltip?: string;
  variant?: CardVariant;
  footer?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function Card({
  title,
  subtitle,
  icon,
  tooltip,
  variant = 'panel',
  footer,
  className = '',
  bodyClassName = '',
  children,
}: CardProps) {
  return (
    <section className={`card card--${variant} ${className}`}>
      <header className="card__header">
        {icon && <span className="card__icon">{icon}</span>}
        <div className="card__heading">
          <h2 className="card__title">
            {title}
            {tooltip && <InfoTip text={tooltip} />}
          </h2>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </div>
      </header>
      <div className={`card__body ${bodyClassName}`}>{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </section>
  );
}
