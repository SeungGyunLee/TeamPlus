import React from 'react';
import { Modal, Pressable, View } from 'react-native';
import { useTheme } from '../theme/theme';
import { Button, Card, T } from './ui';
export function Confirm({ visible, title, children, confirmLabel = '확인', onCancel, onConfirm }: React.PropsWithChildren<{ visible: boolean; title: string; confirmLabel?: string; onCancel: () => void; onConfirm: () => void }>) {
  const { colors: c } = useTheme();
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel} statusBarTranslucent><View style={{ flex: 1, justifyContent: 'center', padding: 24 }}>
    <Pressable accessibilityLabel="닫기" onPress={onCancel} style={{ position: 'absolute', inset: 0, backgroundColor: c.shadow, opacity: 0.65 }}/>
    <Card accessibilityViewIsModal style={{ maxWidth: 450, width: '100%', alignSelf: 'center', gap: 20 }}><T size={23} bold accessibilityRole="header">{title}</T>{children}<Button onPress={onConfirm}>{confirmLabel}</Button><Button variant="ghost" onPress={onCancel}>돌아가기</Button></Card>
  </View></Modal>;
}
