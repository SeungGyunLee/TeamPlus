// Adapted from React Native Reusables Button (MIT). See licenses/react-native-reusables.txt.
// Source: packages/registry/src/nativewind/components/ui/button.tsx
// https://github.com/founded-labs/react-native-reusables
import React from 'react';
import { Pressable, Text } from 'react-native';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useTheme } from '../../theme/theme';
const buttonVariants = cva('flex-row items-center justify-center rounded-xl border px-5 py-3.5', {
  variants: { variant: { default: 'bg-primary border-primary', outline: 'bg-transparent', ghost: 'border-transparent bg-transparent' }, size: { default: 'min-h-12', sm: 'min-h-11 px-3 py-2' } },
  defaultVariants: { variant: 'default', size: 'default' },
});
export function Button({ children, variant = 'default', size, className, disabled, ...props }: React.ComponentProps<typeof Pressable> & VariantProps<typeof buttonVariants>) {
  const { colors: c } = useTheme();
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: !!disabled }} disabled={disabled} {...props} className={twMerge(clsx(buttonVariants({ variant, size }), className))} style={({ pressed }) => [{ opacity: disabled ? 0.65 : pressed ? 0.72 : 1, borderColor: variant === 'outline' ? c.border : variant === 'ghost' ? 'transparent' : c.primary }]}>
    {typeof children === 'string' ? <Text style={{ fontFamily: 'Pretendard-SemiBold', fontSize: 15, color: variant === 'default' ? c.onPrimary : c.primary }}>{children}</Text> : children as React.ReactNode}
  </Pressable>;
}
