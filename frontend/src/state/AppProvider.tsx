import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppData } from '../domain/model';
import { LocalRepository } from '../data/repository';
const repository = new LocalRepository(AsyncStorage);
interface AppContextValue {
  data: AppData | null; loading: boolean; error: string | null; saveError: string | null; saving: boolean;
  update: (change: (current: AppData) => AppData) => void;
  reload: () => Promise<void>; retrySave: () => void; repository: LocalRepository;
}
const AppContext = createContext<AppContextValue | null>(null);
export function AppProvider({ children }: React.PropsWithChildren) {
  const [data, setData] = useState<AppData | null>(null);
  const current = useRef<AppData | null>(null);
  const revision = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const reload = useCallback(async () => {
    setLoading(true); setError(null);
    try { const loaded = await repository.load(); current.current = loaded; setData(loaded); }
    catch (e) { setError(e instanceof Error ? e.message : '기기 저장소에 접근할 수 없어요.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  const persist = useCallback((next: AppData) => {
    const version = ++revision.current;
    setSaving(true);
    void repository.save(next).then(() => {
      if (version === revision.current) { setSaveError(null); setSaving(false); }
    }).catch(() => {
      if (version === revision.current) { setSaveError('기기에 저장하지 못했어요. 앱을 닫기 전에 다시 시도해 주세요.'); setSaving(false); }
    });
  }, []);
  const update = useCallback((change: (current: AppData) => AppData) => {
    if (!current.current) throw new Error('데이터를 불러오는 중이에요.');
    // Synchronous ref prevents two rapid booking actions using a stale snapshot.
    const next = change(current.current);
    current.current = next; setData(next); persist(next);
  }, [persist]);
  const retrySave = useCallback(() => { if (current.current) persist(current.current); }, [persist]);
  return <AppContext.Provider value={{ data, loading, error, saveError, saving, update, reload, retrySave, repository }}>{children}</AppContext.Provider>;
}
export function useApp() { const value = useContext(AppContext); if (!value) throw new Error('AppProvider is required'); return value; }
