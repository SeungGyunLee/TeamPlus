import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { api, errorMessage } from '../data/api';
import { useApp } from './AppProvider';

type Resource<T> = { value?: T; loading: boolean; error?: string };

export function useResource<T>(load: (signal: AbortSignal) => Promise<T> | undefined) {
  const [resource, setResource] = useState<Resource<T>>({ loading: true });
  const current = useRef<AbortController | null>(null);
  const reload = useCallback(() => {
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    setResource({ loading: true });
    const request = load(controller.signal);
    if (!request) setResource({ loading: false });
    else void request.then(
      value => { if (!controller.signal.aborted) setResource({ value, loading: false }); },
      error => { if (!controller.signal.aborted) setResource({ error: errorMessage(error), loading: false }); },
    );
  }, [load]);
  useFocusEffect(useCallback(() => {
    reload();
    return () => current.current?.abort();
  }, [reload]));
  return { ...resource, reload };
}

export function useGroup(id: string) {
  const { data } = useApp();
  const resource = useResource(useCallback(signal => api?.group(id, signal), [id]));
  return { ...resource, group: api ? resource.value : data?.groups.find(group => group.id === id) };
}

export function useTask() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const running = useRef(false);
  async function run(action: () => Promise<unknown>) {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setError('');
    try { await action(); }
    catch (failure) { setError(errorMessage(failure)); }
    finally { running.current = false; setBusy(false); }
  }
  return { busy, error, run, clearError: () => setError('') };
}
