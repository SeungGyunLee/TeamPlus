import React from 'react';
import { Pressable, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming, ReduceMotion } from 'react-native-reanimated';
import { DAYS, PERIODS, Day, SlotKey } from '../domain/model';
import { useTheme } from '../theme/theme';
import { Row, T } from './ui';
function Cell({ label, selected, background, textColor, accessibilityLabel, onPress }: { label: string; selected?: boolean; background: string; textColor: string; accessibilityLabel: string; onPress: () => void }) {
  const { colors: c } = useTheme(); const scale = useSharedValue(1);
  const style = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return <Animated.View style={[{ flex: 1 }, style]}><Pressable accessibilityRole="button" accessibilityState={{ selected }} accessibilityLabel={accessibilityLabel} onPress={onPress} onPressIn={() => { scale.value = withTiming(0.94, { duration: 90, reduceMotion: ReduceMotion.System }); }} onPressOut={() => { scale.value = withTiming(1, { duration: 120, reduceMotion: ReduceMotion.System }); }} style={{ minHeight: 56, backgroundColor: background, borderWidth: selected ? 2 : 1, borderColor: selected ? c.primary : c.border, borderRadius: 8, justifyContent: 'center', alignItems: 'center' }}><T size={12} bold color={textColor}>{label}</T></Pressable></Animated.View>;
}
export function TimetableGrid({ cell, onPress }: { cell: (key: SlotKey) => { label: string; selected?: boolean; background: string; textColor: string; description: string }; onPress: (key: SlotKey) => void }) {
  return <View style={{ gap: 6 }}><Row style={{ gap: 4, paddingBottom: 5 }}><View style={{ width: 40 }}/>{DAYS.map(d => <T key={d} size={12} muted style={{ flex: 1, textAlign: 'center' }}>{d}</T>)}</Row>
    {PERIODS.map((time, period) => <Row key={period} style={{ gap: 4 }}><View style={{ width: 40 }}><T size={12} bold>{period + 1}</T><T size={9} muted>{time.slice(0,5)}{'\n'}{time.slice(6)}</T></View>{DAYS.map((day, index) => { const key: SlotKey = `${index as Day}-${period}`; const value = cell(key); return <Cell key={key} {...value} accessibilityLabel={`${day}요일 ${period + 1}교시 ${time} ${value.description}`} onPress={() => onPress(key)}/>; })}</Row>)}
  </View>;
}
