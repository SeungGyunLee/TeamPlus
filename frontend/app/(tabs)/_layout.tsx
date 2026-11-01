import { Tabs } from 'expo-router';
import { House, MapPin, CalendarCheck2, Settings2 } from 'lucide-react-native';
import { useTheme } from '../../src/theme/theme';
export default function TabLayout() {
  const { colors: c } = useTheme();
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: c.primary, tabBarInactiveTintColor: c.muted, tabBarStyle: { backgroundColor: c.surface, borderTopColor: c.border, paddingTop: 8, height: 72 }, tabBarLabelStyle: { fontFamily: 'Pretendard-SemiBold', fontSize: 11, paddingBottom: 5 } }}>
    <Tabs.Screen name="index" options={{ title: '홈', tabBarIcon: ({ color }) => <House size={21} color={color}/> }}/>
    <Tabs.Screen name="places" options={{ title: '장소', tabBarIcon: ({ color }) => <MapPin size={21} color={color}/> }}/>
    <Tabs.Screen name="reservations" options={{ title: '내 예약', tabBarIcon: ({ color }) => <CalendarCheck2 size={21} color={color}/> }}/>
    <Tabs.Screen name="settings" options={{ title: '설정', tabBarIcon: ({ color }) => <Settings2 size={21} color={color}/> }}/>
  </Tabs>;
}
