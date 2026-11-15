import React, { useState } from 'react';
import { Linking, Platform } from 'react-native';
import { openApplication } from 'expo-intent-launcher';
import { Button, T } from './ui';

// Android package from the library's official Play listing.
const LIBRARY_PACKAGE = 'idoit.slpck.kwangwoon';
const LIBRARY_WEB = 'https://www.kw.ac.kr/ko/department/affiliated03.jsp';

export function LibraryLink() {
  const [message, setMessage] = useState('');
  function openLibrary() {
    try {
      if (Platform.OS === 'android') {
        openApplication(LIBRARY_PACKAGE);
        setMessage('');
      } else {
        setMessage('중앙도서관 안내에서 이용 방법을 확인해 주세요.');
      }
    } catch {
      setMessage('중앙도서관 앱을 열 수 없어요. 앱을 설치하거나 공식 안내를 확인해 주세요.');
    }
  }
  function openUrl(url: string) {
    void Linking.openURL(url).catch(() => setMessage('링크를 열 수 없어요. 브라우저 연결을 확인해 주세요.'));
  }
  return <>
    <Button onPress={openLibrary}>중앙도서관 앱 열기</Button>
    {message && <T muted accessibilityRole="alert">{message}</T>}
    <Button variant="outline" onPress={() => openUrl(LIBRARY_WEB)}>중앙도서관 공식 안내</Button>
    {message && Platform.OS === 'android' && <Button variant="ghost" onPress={() => openUrl('https://play.google.com/store/apps/details?id=' + LIBRARY_PACKAGE)}>Google Play에서 앱 보기</Button>}
  </>;
}
