import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ChatEntryProps extends React.HTMLAttributes<HTMLLIElement> {
  /** The locale to use for the timestamp. */
  locale: string;
  /** The timestamp of the message. */
  timestamp: number;
  /** The message to display. */
  message: string;
  /** The origin of the message. */
  messageOrigin: 'local' | 'remote';
  /** The sender's name. */
  name?: string;
  /** Whether the message has been edited. */
  hasBeenEdited?: boolean;
}

export const ChatEntry = ({
  name,
  locale,
  timestamp,
  message,
  messageOrigin,
  hasBeenEdited = false,
  className,
  ...props
}: ChatEntryProps) => {
  const time = new Date(timestamp);
  const title = time.toLocaleTimeString(locale, { timeStyle: 'full' });

  // Display name for shopping assistant
  const displayName = name || (messageOrigin === 'local' ? 'You' : 'Shopping Assistant');

  return (
    <li
      title={title}
      data-lk-message-origin={messageOrigin}
      className={cn('group flex w-full flex-col gap-0.5', className)}
      {...props}
    >
      <header
        className={cn(
          'text-muted-foreground flex items-center gap-2 text-sm font-semibold',
          messageOrigin === 'local' ? 'flex-row-reverse' : 'text-left'
        )}
      >
        <strong className={messageOrigin === 'local' ? 'text-primary' : 'text-accent'}>
          {displayName}
        </strong>
        <span className="font-mono text-xs opacity-50 transition-opacity ease-linear group-hover:opacity-100">
          {hasBeenEdited && '*'}
          {time.toLocaleTimeString(locale, { timeStyle: 'short' })}
        </span>
      </header>
      <span
        className={cn(
          'max-w-4/5 rounded-[20px] p-3 text-base leading-relaxed',
          messageOrigin === 'local'
            ? 'bg-muted ml-auto border border-primary/20'
            : 'mr-auto bg-accent/10 border border-accent/20'
        )}
      >
        {message}
      </span>
    </li>
  );
};
