import React from 'react';
import { View } from 'react-native';
import { Check, Monitor, Moon, Sun } from 'lucide-react-native';
import { Button, Card, Row, Screen, Section, T } from '../../src/components/ui';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
import { ThemeMode } from '../../src/domain/model';
const OPTIONS = [{ value: 'light', label: '라이트 모드', description: '따뜻한 아이보리와 버건디', Icon: Sun }, { value: 'dark', label: '다크 모드', description: '차분한 차콜과 부드러운 대비', Icon: Moon }, { value: 'system', label: '기기 설정에 따름', description: '시스템 테마를 자동으로 반영', Icon: Monitor }] as const;
export default function Settings() {
  const { data, update } = useApp(); const { colors: c } = useTheme();
  return <Screen title="나에게 맞는 환경" eyebrow="PREFERENCES"><Section title="화면 테마"/><T muted>처음에는 라이트 모드로 시작해요.{'\n'}선택한 설정은 앱을 다시 열어도 유지됩니다.</T>
    <View style={{ gap: 10 }}>{OPTIONS.map(({ value, label, description, Icon }) => <Button key={value} variant="outline" accessibilityRole="radio" accessibilityState={{ checked: data?.theme === value }} accessibilityLabel={label} onPress={() => update(d => ({ ...d, theme: value as ThemeMode }))}><Row style={{ flex: 1 }}><Icon size={22} color={c.primary}/><View style={{ flex: 1, gap: 3 }}><T bold>{label}</T><T size={12} muted>{description}</T></View>{data?.theme === value && <Check size={20} color={c.primary}/>}</Row></Button>)}</View>
    <Section title="KW Meet 안내"/><Card><T size={24} bold>KW Meet <T size={12} muted>1.0.0 · MVP</T></T><T size={13} muted>광운대학교 학생들의 모임 일정 조율을 위한 독립 시연 앱입니다. 대학의 공식 서비스가 아닙니다.</T><T size={13} muted>모임·시간표·예약은 이 기기에 저장됩니다. 계정, 클라우드 동기화, 실제 예약 및 AI 추천은 제공하지 않습니다.</T><T size={13} muted>앱 데이터를 삭제하거나 앱을 제거하면 저장된 내용이 사라질 수 있습니다.</T></Card>
    <Section title="오픈소스 및 디자인"/><Card><T bold>Pretendard · SIL OFL 1.1</T><T size={12} muted>Copyright © 2021 Kil Hyung-jin. 원본 폰트와 라이선스를 함께 배포합니다.</T><T bold>React Native Reusables · MIT</T><T size={12} muted>공통 버튼을 앱 토큰에 맞게 수정해 사용했습니다. React / React Native / Expo / NativeWind / Reanimated 및 AsyncStorage의 오픈소스 라이선스를 준수합니다.</T><T size={12} muted>Lucide 아이콘 · ISC. 전체 라이브러리와 라이선스 원문은 프로젝트의 THIRD_PARTY_NOTICES.md 및 licenses 폴더에 있습니다.</T><T size={12} muted>공식 대학 심볼을 사용하지 않았으며, 버건디 색상은 KW Meet 자체 디자인 팔레트입니다.</T></Card>
  </Screen>;
}
