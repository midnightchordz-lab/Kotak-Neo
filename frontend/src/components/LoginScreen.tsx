import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  SafeAreaView,
} from 'react-native';
import { colors, spacing } from '../theme/colors';
import axios from 'axios';
import Constants from 'expo-constants';

const API_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface LoginScreenProps {
  onLoginSuccess: () => void;
  onSkipToDemo: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLoginSuccess, onSkipToDemo }) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [totp, setTotp] = useState('');
  const [mpin, setMpin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sid, setSid] = useState('');

  const handleTotpSubmit = async () => {
    if (totp.length !== 6) {
      setError('TOTP must be 6 digits');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_URL}/api/auth/totp`, { totp });
      if (response.data.success) {
        setSid(response.data.sid);
        setStep(2);
        setError('');
      } else {
        setError(response.data.error || 'TOTP validation failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'TOTP validation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleMpinSubmit = async () => {
    if (mpin.length !== 4) {
      setError('MPIN must be 4 digits');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_URL}/api/auth/mpin`, { mpin });
      if (response.data.success) {
        onLoginSuccess();
      } else {
        setError(response.data.error || 'MPIN validation failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'MPIN validation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.logo}>COSTAR</Text>
            <Text style={styles.title}>Kotak Neo F&O AlgoTrader</Text>
            <Text style={styles.subtitle}>Professional Intraday Trading System</Text>
          </View>

          {/* Login Card */}
          <View style={styles.card}>
            <View style={styles.stepIndicator}>
              <View style={[styles.stepDot, step >= 1 && styles.stepDotActive]} />
              <View style={styles.stepLine} />
              <View style={[styles.stepDot, step >= 2 && styles.stepDotActive]} />
            </View>
            <Text style={styles.stepText}>
              Step {step} of 2: {step === 1 ? 'TOTP Verification' : 'MPIN Verification'}
            </Text>

            {step === 1 ? (
              <>
                <Text style={styles.label}>Enter 6-digit TOTP</Text>
                <Text style={styles.hint}>
                  Open your authenticator app linked to Kotak NEO
                </Text>
                <TextInput
                  style={styles.input}
                  value={totp}
                  onChangeText={(text) => setTotp(text.replace(/[^0-9]/g, '').slice(0, 6))}
                  placeholder="000000"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="number-pad"
                  maxLength={6}
                  autoFocus
                />
                <TouchableOpacity
                  style={[styles.button, loading && styles.buttonDisabled]}
                  onPress={handleTotpSubmit}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="white" />
                  ) : (
                    <Text style={styles.buttonText}>VERIFY TOTP</Text>
                  )}
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={styles.label}>Enter 4-digit MPIN</Text>
                <Text style={styles.hint}>
                  Your Kotak NEO trading MPIN
                </Text>
                <TextInput
                  style={styles.input}
                  value={mpin}
                  onChangeText={(text) => setMpin(text.replace(/[^0-9]/g, '').slice(0, 4))}
                  placeholder="••••"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="number-pad"
                  maxLength={4}
                  secureTextEntry
                  autoFocus
                />
                <TouchableOpacity
                  style={[styles.button, loading && styles.buttonDisabled]}
                  onPress={handleMpinSubmit}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="white" />
                  ) : (
                    <Text style={styles.buttonText}>CONNECT TO KOTAK</Text>
                  )}
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.backButton}
                  onPress={() => {
                    setStep(1);
                    setMpin('');
                    setError('');
                  }}
                >
                  <Text style={styles.backButtonText}>← Back to TOTP</Text>
                </TouchableOpacity>
              </>
            )}

            {error ? (
              <View style={styles.errorContainer}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}
          </View>

          {/* Demo Mode Option */}
          <View style={styles.demoSection}>
            <Text style={styles.demoText}>Don't have credentials?</Text>
            <TouchableOpacity style={styles.demoButton} onPress={onSkipToDemo}>
              <Text style={styles.demoButtonText}>CONTINUE IN DEMO MODE</Text>
            </TouchableOpacity>
            <Text style={styles.demoHint}>
              Demo mode uses simulated market data and paper trading
            </Text>
          </View>

          {/* Info Section */}
          <View style={styles.infoSection}>
            <Text style={styles.infoTitle}>Features</Text>
            <View style={styles.featureRow}>
              <Text style={styles.featureIcon}>◉</Text>
              <Text style={styles.featureText}>10 Technical Indicators Confluence</Text>
            </View>
            <View style={styles.featureRow}>
              <Text style={styles.featureIcon}>◉</Text>
              <Text style={styles.featureText}>AI Signal Validation (Claude)</Text>
            </View>
            <View style={styles.featureRow}>
              <Text style={styles.featureIcon}>◉</Text>
              <Text style={styles.featureText}>ATR-based Risk Management</Text>
            </View>
            <View style={styles.featureRow}>
              <Text style={styles.featureIcon}>◉</Text>
              <Text style={styles.featureText}>Backtesting with Win Rate Analysis</Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: spacing.md,
  },
  header: {
    alignItems: 'center',
    marginTop: 40,
    marginBottom: 30,
  },
  logo: {
    fontSize: 36,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 8,
  },
  subtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  stepIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  stepDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.bgTertiary,
    borderWidth: 2,
    borderColor: colors.border,
  },
  stepDotActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  stepLine: {
    width: 60,
    height: 2,
    backgroundColor: colors.border,
    marginHorizontal: 8,
  },
  stepText: {
    color: colors.textSecondary,
    fontSize: 13,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  label: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  hint: {
    color: colors.textMuted,
    fontSize: 12,
    marginBottom: spacing.md,
  },
  input: {
    backgroundColor: colors.bgTertiary,
    borderRadius: 8,
    padding: 16,
    fontSize: 24,
    fontFamily: 'monospace',
    color: colors.text,
    textAlign: 'center',
    letterSpacing: 8,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: 'white',
    fontSize: 15,
    fontWeight: '700',
  },
  backButton: {
    marginTop: spacing.md,
    alignItems: 'center',
  },
  backButtonText: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  errorContainer: {
    backgroundColor: colors.bearish + '20',
    borderRadius: 6,
    padding: spacing.sm,
    marginTop: spacing.md,
  },
  errorText: {
    color: colors.bearish,
    fontSize: 13,
    textAlign: 'center',
  },
  demoSection: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  demoText: {
    color: colors.textMuted,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  demoButton: {
    backgroundColor: colors.bgTertiary,
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  demoButtonText: {
    color: colors.warning,
    fontSize: 13,
    fontWeight: '600',
  },
  demoHint: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 8,
  },
  infoSection: {
    backgroundColor: colors.bgSecondary,
    borderRadius: 8,
    padding: spacing.md,
  },
  infoTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: spacing.sm,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  featureIcon: {
    color: colors.bullish,
    fontSize: 10,
    marginRight: 8,
  },
  featureText: {
    color: colors.textSecondary,
    fontSize: 12,
  },
});
