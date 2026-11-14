import React, { createContext, useContext, useState } from 'react';
import type { RecommendationResponse } from '../data/api';

interface RecommendationRun {
  groupId: string;
  from: string;
  to: string;
  response: RecommendationResponse;
}
const Context = createContext<{ result?: RecommendationRun; setResult: (result: RecommendationRun) => void } | null>(null);

export function RecommendationProvider({ children }: React.PropsWithChildren) {
  const [result, setResult] = useState<RecommendationRun>();
  return <Context.Provider value={{ result, setResult }}>{children}</Context.Provider>;
}

export function useRecommendation() {
  const context = useContext(Context);
  if (!context) throw new Error('RecommendationProvider is missing');
  return context;
}
