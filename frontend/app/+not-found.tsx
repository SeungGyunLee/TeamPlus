import { router } from 'expo-router';
import { Button, Screen, T } from '../src/components/ui';
export default function NotFound() { return <Screen title="페이지를 찾을 수 없어요"><T muted>주소를 확인하거나 홈으로 이동해 주세요.</T><Button onPress={() => router.replace('/')}>홈으로</Button></Screen>; }
