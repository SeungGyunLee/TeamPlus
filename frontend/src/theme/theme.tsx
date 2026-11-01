import React, { createContext, useContext } from 'react';
import { useColorScheme, View } from 'react-native';
import { vars } from 'nativewind';
import Animated, { useAnimatedStyle, withTiming, ReduceMotion } from 'react-native-reanimated';
import { useApp } from '../state/AppProvider';
export const light = {
  background: '#F7F5F0', surface: '#FFFFFF', elevated: '#F0ECE6', primary: '#773344', onPrimary: '#FFFFFF', foreground: '#262126', muted: '#766E72', border: '#E5DFDA', soft: '#EFE1E4', success: '#34624E', successBg: '#E7EFE9', warning: '#805B28', warningBg: '#F4EAD7', occupied: '#EAE5E1', shadow: '#35212A',
};
export type Tokens = typeof light;
export const dark: Tokens = {
  background: '#141518', surface: '#212226', elevated: '#2B2A30', primary: '#D69AAB', onPrimary: '#28151E', foreground: '#F6F1ED', muted: '#B5ADB2', border: '#39383D', soft: '#3B2832', success: '#A3CFB6', successBg: '#23392F', warning: '#E1C28F', warningBg: '#3C3224', occupied: '#343238', shadow: '#08090B',
};
const ThemeContext = createContext({ colors: light, isDark: false });
export function ThemeProvider({ children }: React.PropsWithChildren) {
  const system = useColorScheme();
  const { data } = useApp();
  const mode = data?.theme ?? 'light';
  const isDark = mode === 'dark' || (mode === 'system' && system === 'dark');
  const colors = isDark ? dark : light;
  const animatedCanvas = useAnimatedStyle(() => ({ backgroundColor: withTiming(colors.background, { duration: 180, reduceMotion: ReduceMotion.System }) }), [colors.background]);
  const variables = vars({ '--primary': isDark ? '214 154 171' : '119 51 68', '--canvas': isDark ? '20 21 24' : '247 245 240', '--ink': isDark ? '246 241 237' : '38 33 38' });
  return <ThemeContext.Provider value={{ colors, isDark }}><Animated.View style={[{ flex: 1 }, variables, animatedCanvas]}>{children}</Animated.View></ThemeContext.Provider>;
}
export function useTheme() { return useContext(ThemeContext); }
