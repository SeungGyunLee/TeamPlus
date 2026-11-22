import React, { createContext, useContext, useState } from 'react';
import type { ShareDraft } from '../domain/collaboration';

const Context = createContext<{ draft?: ShareDraft; setDraft: (draft: ShareDraft) => void } | null>(null);

export function ShareProvider({ children }: React.PropsWithChildren) {
  const [draft, setDraft] = useState<ShareDraft>();
  return <Context.Provider value={{ draft, setDraft }}>{children}</Context.Provider>;
}

export function useShareDraft() {
  const context = useContext(Context);
  if (!context) throw new Error('ShareProvider is missing');
  return context;
}
