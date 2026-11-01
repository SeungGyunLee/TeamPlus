import React from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, TextInputProps, View, ViewProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, { FadeIn, ReduceMotion, useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { router } from 'expo-router';
import { ArrowLeft, ArrowUpRight, ChevronRight } from 'lucide-react-native';
import { useTheme } from '../theme/theme';
export { Button } from './ui/button';
const AnimatedSafeAreaView = Animated.createAnimatedComponent(SafeAreaView);
export function T({ children, size = 15, muted, bold, color, style, ...props }: React.ComponentProps<typeof Text> & { size?: number; muted?: boolean; bold?: boolean; color?: string }) {
  const { colors: c } = useTheme();
  return <Text {...props} style={[{ fontFamily: bold ? 'Pretendard-SemiBold' : 'Pretendard', fontSize: size, lineHeight: size * 1.48, color: color ?? (muted ? c.muted : c.foreground) }, style]}>{children}</Text>;
}
export function Row({ children, style, ...props }: ViewProps) { return <View {...props} style={[{ flexDirection: 'row', alignItems: 'center', gap: 12 }, style]}>{children}</View>; }
export function Card({ children, style, ...props }: ViewProps) {
  const { colors: c } = useTheme();
  return <View {...props} style={[{ backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: 16, padding: 20, gap: 14 }, style]}>{children}</View>;
}
export function Screen({ children, title, eyebrow, back = false, action }: React.PropsWithChildren<{ title: string; eyebrow?: string; back?: boolean; action?: React.ReactNode }>) {
  const { colors: c } = useTheme();
  const animatedCanvas = useAnimatedStyle(() => ({ backgroundColor: withTiming(c.background, { duration: 180, reduceMotion: ReduceMotion.System }) }), [c.background]);
  return <AnimatedSafeAreaView edges={['top','left','right','bottom']} style={[{ flex: 1 }, animatedCanvas]}><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 24, paddingBottom: 40, gap: 24, maxWidth: 620, width: '100%', alignSelf: 'center' }}>
      <Animated.View entering={FadeIn.duration(180).reduceMotion(ReduceMotion.System)} style={{ gap: 12 }}>
        {back && <Pressable onPress={() => router.canGoBack() ? router.back() : router.replace('/')} accessibilityRole="button" accessibilityLabel="뒤로 가기" style={{ minHeight: 44, width: 48, justifyContent: 'center' }}><ArrowLeft size={22} color={c.foreground}/></Pressable>}
        <Row style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}><View style={{ flex: 1, gap: 6 }}>{eyebrow && <T size={11} color={c.primary} bold style={{ letterSpacing: 2 }}>{eyebrow}</T>}<T size={30} bold style={{ letterSpacing: -1 }}>{title}</T></View>{action}</Row>
      </Animated.View>{children}
    </ScrollView>
  </KeyboardAvoidingView></AnimatedSafeAreaView>;
}
export function Field(props: TextInputProps) {
  const { colors: c } = useTheme();
  return <TextInput placeholderTextColor={c.muted} maxLength={40} {...props} style={[{ minHeight: 50, backgroundColor: c.surface, color: c.foreground, borderWidth: 1, borderColor: c.border, borderRadius: 10, paddingHorizontal: 14, fontFamily: 'Pretendard', fontSize: 16 }, props.style]} />;
}
export function Chip({ label, selected, onPress, accessibilityLabel }: { label: string; selected?: boolean; onPress?: () => void; accessibilityLabel?: string }) {
  const { colors: c } = useTheme();
  return <Pressable accessibilityLabel={accessibilityLabel ?? label} accessibilityRole={onPress ? 'button' : 'text'} accessibilityState={{ selected }} onPress={onPress} style={({ pressed }) => ({ minHeight: 44, paddingHorizontal: 15, justifyContent: 'center', borderRadius: 10, borderWidth: 1, borderColor: selected ? c.primary : c.border, backgroundColor: selected ? c.soft : c.surface, opacity: pressed ? 0.7 : 1 })}><T size={13} bold={selected} color={selected ? c.primary : c.muted}>{label}</T></Pressable>;
}
export function Section({ title, extra }: { title: string; extra?: string }) { return <Row style={{ justifyContent: 'space-between' }}><T size={18} bold>{title}</T>{extra && <T size={12} muted>{extra}</T>}</Row>; }
export function Badge({ children, tone = 'primary' }: React.PropsWithChildren<{ tone?: 'primary' | 'success' | 'muted' }>) {
  const { colors: c } = useTheme();
  return <View style={{ paddingHorizontal: 9, paddingVertical: 5, borderRadius: 6, alignSelf: 'flex-start', backgroundColor: tone === 'success' ? c.successBg : tone === 'primary' ? c.soft : c.elevated }}><T size={11} bold color={tone === 'success' ? c.success : tone === 'primary' ? c.primary : c.muted}>{children}</T></View>;
}
export function LinkRow({ title, description, onPress, arrow = false }: { title: string; description: string; onPress: () => void; arrow?: boolean }) {
  const { colors: c } = useTheme();
  return <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}><Card><Row><View style={{ flex: 1, gap: 4 }}><T size={17} bold>{title}</T><T size={13} muted>{description}</T></View>{arrow ? <ArrowUpRight color={c.primary} size={22}/> : <ChevronRight color={c.muted} size={20}/>}</Row></Card></Pressable>;
}
export function Empty({ title, description }: { title: string; description: string }) { return <Card><T size={19} bold>{title}</T><T muted>{description}</T></Card>; }
export function Loading() { const { colors: c } = useTheme(); return <View style={{ padding: 40, alignItems: 'center', gap: 16 }}><ActivityIndicator color={c.primary}/><T muted>기기에 저장한 내용을 불러오고 있어요.</T></View>; }
