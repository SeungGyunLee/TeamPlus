import '../global.css';
import React, { useEffect } from 'react';
import { Platform, View } from 'react-native';
import { Stack } from 'expo-router';
import { useFonts } from 'expo-font';
import { StatusBar } from 'expo-status-bar';
import { NavigationBar } from 'expo-navigation-bar';
import * as SystemUI from 'expo-system-ui';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PortalHost } from '@rn-primitives/portal';
import { AppProvider, useApp } from '../src/state/AppProvider';
import { ThemeProvider, useTheme } from '../src/theme/theme';
import { Button, Loading, Screen, T } from '../src/components/ui';
function Content() {
  const { colors: c, isDark } = useTheme();
  const { loading, error, reload, saveError, saving, retrySave } = useApp();
  const [fontsLoaded, fontError] = useFonts({ Pretendard: require('../assets/fonts/Pretendard-Regular.otf'), 'Pretendard-SemiBold': require('../assets/fonts/Pretendard-SemiBold.otf') });
  useEffect(() => { void SystemUI.setBackgroundColorAsync(c.background).catch(() => {}); }, [c.background]);
  if (loading || (!fontsLoaded && !fontError)) return <Screen title="KW Meet"><Loading/></Screen>;
  if (error) return <Screen title="잠시 확인해 주세요"><T muted>{error}</T><Button onPress={() => void reload()}>다시 불러오기</Button></Screen>;
  return <><StatusBar style={isDark ? 'light' : 'dark'}/>{Platform.OS === 'android' && <NavigationBar style={isDark ? 'light' : 'dark'}/>}<Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.background }, animation: 'slide_from_right' }}><Stack.Screen name="(tabs)"/><Stack.Screen name="group/[id]"/><Stack.Screen name="timetable/[id]"/><Stack.Screen name="availability/[id]"/><Stack.Screen name="place/[id]"/><Stack.Screen name="booking"/></Stack>
    {(saveError || saving) && <View accessibilityLiveRegion="polite" style={{ backgroundColor: saveError ? c.warningBg : c.surface, padding: 12, borderTopWidth: 1, borderColor: c.border }}><T size={12} color={saveError ? c.warning : c.muted}>{saveError ?? '변경사항 저장 중…'}</T>{saveError && <Button size="sm" variant="ghost" onPress={retrySave}>저장 다시 시도</Button>}</View>}<PortalHost/></>;
}
export default function RootLayout() { return <SafeAreaProvider><AppProvider><ThemeProvider><Content/></ThemeProvider></AppProvider></SafeAreaProvider>; }
