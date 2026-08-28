import type { ReactNode } from 'react';
import './Card.css';

export type CardVariant = 'panel' | 'red' | 'blue' | 'teal';

interface CardProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
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
          <h2 className="card__title">{title}</h2>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </div>
      </header>
      <div className={`card__body ${bodyClassName}`}>{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </section>
  );
}
