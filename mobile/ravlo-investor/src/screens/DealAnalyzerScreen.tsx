import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';

type Strategy = 'fix_and_flip' | 'brrrr' | 'buy_and_hold' | 'wholesale';

const STRATEGIES: { key: Strategy; label: string; icon: string; color: string }[] = [
  { key: 'fix_and_flip', label: 'Fix & Flip', icon: 'hammer-outline', color: Colors.warning },
  { key: 'brrrr', label: 'BRRRR', icon: 'repeat-outline', color: Colors.blueprint },
  { key: 'buy_and_hold', label: 'Buy & Hold', icon: 'home-outline', color: Colors.success },
  { key: 'wholesale', label: 'Wholesale', icon: 'swap-horizontal-outline', color: Colors.info },
];

interface Inputs {
  purchasePrice: string;
  rehabCost: string;
  arv: string;
  closingCosts: string;
  holdingMonths: string;
  holdingCostPerMonth: string;
  sellPrice: string;
  agentFeePercent: string;
  assignmentFee: string;
  monthlyRent: string;
  monthlyExpenses: string;
  refinanceLTV: string;
  refinanceRate: string;
}

const DEFAULT: Inputs = {
  purchasePrice: '',
  rehabCost: '',
  arv: '',
  closingCosts: '',
  holdingMonths: '',
  holdingCostPerMonth: '',
  sellPrice: '',
  agentFeePercent: '6',
  assignmentFee: '',
  monthlyRent: '',
  monthlyExpenses: '',
  refinanceLTV: '75',
  refinanceRate: '7.5',
};

function n(s: string): number {
  return parseFloat(s.replace(/,/g, '')) || 0;
}

function fmt(val: number, decimals = 0): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(val);
}

export default function DealAnalyzerScreen() {
  const [strategy, setStrategy] = useState<Strategy>('fix_and_flip');
  const [inputs, setInputs] = useState<Inputs>(DEFAULT);

  const set = useCallback((key: keyof Inputs, val: string) => {
    setInputs(prev => ({ ...prev, [key]: val }));
  }, []);

  const purchase = n(inputs.purchasePrice);
  const rehab = n(inputs.rehabCost);
  const arv = n(inputs.arv);
  const closing = n(inputs.closingCosts);
  const holdMonths = n(inputs.holdingMonths) || 6;
  const holdCost = n(inputs.holdingCostPerMonth);
  const totalHolding = holdMonths * holdCost;
  const agentPct = n(inputs.agentFeePercent) / 100;
  const allIn = purchase + rehab + closing + totalHolding;

  // Fix & Flip
  const sellPrice = n(inputs.sellPrice) || arv;
  const agentFee = sellPrice * agentPct;
  const flipProfit = sellPrice - agentFee - allIn;
  const flipROI = allIn > 0 ? (flipProfit / allIn) * 100 : 0;
  const flipAnnROI = holdMonths > 0 ? (flipROI / holdMonths) * 12 : 0;
  const maxAllowable = arv * 0.7 - rehab;

  // BRRRR
  const refinanceLTV = n(inputs.refinanceLTV) / 100 || 0.75;
  const refinanceRate = n(inputs.refinanceRate) / 100 || 0.075;
  const refinanceAmount = arv * refinanceLTV;
  const cashRecovered = refinanceAmount - purchase - closing;
  const cashLeft = Math.max(0, allIn - cashRecovered);
  const monthlyPayment = refinanceAmount > 0 ? (refinanceAmount * (refinanceRate / 12)) / (1 - Math.pow(1 + refinanceRate / 12, -360)) : 0;
  const netMonthly = n(inputs.monthlyRent) - n(inputs.monthlyExpenses) - monthlyPayment;
  const cashOnCash = cashLeft > 0 ? (netMonthly * 12 / cashLeft) * 100 : 0;

  // Buy & Hold
  const bhRent = n(inputs.monthlyRent);
  const bhExp = n(inputs.monthlyExpenses);
  const bhNOI = (bhRent - bhExp) * 12;
  const bhCashOnCash = allIn > 0 ? (bhNOI / allIn) * 100 : 0;
  const bhCapRate = arv > 0 ? (bhNOI / arv) * 100 : 0;
  const bhGRM = bhRent > 0 ? purchase / (bhRent * 12) : 0;

  // Wholesale
  const assignFee = n(inputs.assignmentFee);
  const wsCost = closing;
  const wsProfit = assignFee - wsCost;
  const wsROI = wsCost > 0 ? (wsProfit / wsCost) * 100 : 0;

  const renderInputs = () => {
    const common = (
      <>
        <InputRow label="Purchase Price" value={inputs.purchasePrice} onChange={v => set('purchasePrice', v)} prefix="$" />
        <InputRow label="Rehab Cost" value={inputs.rehabCost} onChange={v => set('rehabCost', v)} prefix="$" />
        <InputRow label="ARV (After Repair Value)" value={inputs.arv} onChange={v => set('arv', v)} prefix="$" />
        <InputRow label="Closing Costs" value={inputs.closingCosts} onChange={v => set('closingCosts', v)} prefix="$" />
      </>
    );

    if (strategy === 'fix_and_flip') return (
      <>
        {common}
        <InputRow label="Holding Period (months)" value={inputs.holdingMonths} onChange={v => set('holdingMonths', v)} suffix="mo" />
        <InputRow label="Monthly Holding Cost" value={inputs.holdingCostPerMonth} onChange={v => set('holdingCostPerMonth', v)} prefix="$" />
        <InputRow label="Expected Sale Price" value={inputs.sellPrice} onChange={v => set('sellPrice', v)} prefix="$" placeholder="Defaults to ARV" />
        <InputRow label="Agent Fee %" value={inputs.agentFeePercent} onChange={v => set('agentFeePercent', v)} suffix="%" />
      </>
    );

    if (strategy === 'brrrr') return (
      <>
        {common}
        <InputRow label="Monthly Rent" value={inputs.monthlyRent} onChange={v => set('monthlyRent', v)} prefix="$" />
        <InputRow label="Monthly Expenses (excl. mortgage)" value={inputs.monthlyExpenses} onChange={v => set('monthlyExpenses', v)} prefix="$" />
        <InputRow label="Refinance LTV %" value={inputs.refinanceLTV} onChange={v => set('refinanceLTV', v)} suffix="%" />
        <InputRow label="Refinance Rate %" value={inputs.refinanceRate} onChange={v => set('refinanceRate', v)} suffix="%" />
      </>
    );

    if (strategy === 'buy_and_hold') return (
      <>
        {common}
        <InputRow label="Monthly Rent" value={inputs.monthlyRent} onChange={v => set('monthlyRent', v)} prefix="$" />
        <InputRow label="Monthly Expenses (taxes, ins, mgmt)" value={inputs.monthlyExpenses} onChange={v => set('monthlyExpenses', v)} prefix="$" />
      </>
    );

    if (strategy === 'wholesale') return (
      <>
        <InputRow label="Purchase Price (contract)" value={inputs.purchasePrice} onChange={v => set('purchasePrice', v)} prefix="$" />
        <InputRow label="Assignment Fee" value={inputs.assignmentFee} onChange={v => set('assignmentFee', v)} prefix="$" />
        <InputRow label="Transaction Costs" value={inputs.closingCosts} onChange={v => set('closingCosts', v)} prefix="$" />
        <InputRow label="ARV (for reference)" value={inputs.arv} onChange={v => set('arv', v)} prefix="$" />
      </>
    );
  };

  const renderResults = () => {
    if (strategy === 'fix_and_flip') return (
      <>
        <ResultRow label="All-In Cost" value={fmt(allIn)} />
        <ResultRow label="Sale Price" value={fmt(sellPrice)} />
        <ResultRow label="Agent Fee" value={fmt(agentFee)} color={Colors.danger} />
        <ResultRow label="Net Profit" value={fmt(flipProfit)} color={flipProfit >= 0 ? Colors.success : Colors.danger} large />
        <ResultRow label="ROI" value={`${flipROI.toFixed(1)}%`} color={flipROI >= 15 ? Colors.success : flipROI >= 0 ? Colors.warning : Colors.danger} />
        <ResultRow label="Annualized ROI" value={`${flipAnnROI.toFixed(1)}%`} color={Colors.info} />
        <ResultRow label="Max Allowable Offer (70% rule)" value={fmt(maxAllowable)} color={Colors.blueprint} />
      </>
    );

    if (strategy === 'brrrr') return (
      <>
        <ResultRow label="All-In Cost" value={fmt(allIn)} />
        <ResultRow label="Refinance Amount (at LTV)" value={fmt(refinanceAmount)} color={Colors.blueprint} />
        <ResultRow label="Cash Recovered" value={fmt(cashRecovered)} color={cashRecovered >= allIn ? Colors.success : Colors.warning} />
        <ResultRow label="Cash Left In Deal" value={fmt(cashLeft)} large />
        <ResultRow label="Monthly Mortgage Payment" value={fmt(monthlyPayment)} color={Colors.danger} />
        <ResultRow label="Net Monthly Cash Flow" value={fmt(netMonthly)} color={netMonthly >= 0 ? Colors.success : Colors.danger} />
        <ResultRow label="Cash-on-Cash ROI" value={`${cashOnCash.toFixed(1)}%`} color={cashOnCash >= 8 ? Colors.success : cashOnCash >= 0 ? Colors.warning : Colors.danger} large />
      </>
    );

    if (strategy === 'buy_and_hold') return (
      <>
        <ResultRow label="All-In Cost" value={fmt(allIn)} />
        <ResultRow label="Annual NOI" value={fmt(bhNOI)} color={bhNOI >= 0 ? Colors.success : Colors.danger} />
        <ResultRow label="Cash-on-Cash ROI" value={`${bhCashOnCash.toFixed(1)}%`} color={bhCashOnCash >= 8 ? Colors.success : bhCashOnCash >= 0 ? Colors.warning : Colors.danger} large />
        <ResultRow label="Cap Rate" value={`${bhCapRate.toFixed(1)}%`} color={Colors.blueprint} />
        <ResultRow label="Gross Rent Multiplier" value={`${bhGRM.toFixed(1)}x`} color={Colors.info} />
      </>
    );

    if (strategy === 'wholesale') return (
      <>
        <ResultRow label="Assignment Fee" value={fmt(assignFee)} color={Colors.success} />
        <ResultRow label="Transaction Costs" value={fmt(wsCost)} color={Colors.danger} />
        <ResultRow label="Net Profit" value={fmt(wsProfit)} color={wsProfit >= 0 ? Colors.success : Colors.danger} large />
        <ResultRow label="ROI" value={`${wsROI.toFixed(1)}%`} color={wsROI >= 100 ? Colors.success : Colors.warning} />
        {arv > 0 && <ResultRow label="Max Offer (70% rule - rehab)" value={fmt(arv * 0.7 - rehab)} color={Colors.blueprint} />}
      </>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Deal Analyzer</Text>
        <TouchableOpacity onPress={() => setInputs(DEFAULT)} style={styles.clearBtn}>
          <Ionicons name="refresh-outline" size={18} color={Colors.textMuted} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {/* Strategy selector */}
          <View style={styles.stratRow}>
            {STRATEGIES.map(s => (
              <TouchableOpacity
                key={s.key}
                style={[styles.stratChip, strategy === s.key && { backgroundColor: s.color, borderColor: s.color }]}
                onPress={() => setStrategy(s.key)}
                activeOpacity={0.75}
              >
                <Ionicons name={s.icon as any} size={14} color={strategy === s.key ? Colors.white : s.color} />
                <Text style={[styles.stratLabel, strategy === s.key && { color: Colors.white }]}>{s.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Inputs */}
          <View style={styles.inputsCard}>
            {renderInputs()}
          </View>

          {/* Results */}
          <Text style={styles.sectionTitle}>Analysis</Text>
          <View style={styles.resultsCard}>
            {renderResults()}
          </View>

          {/* Deal score */}
          {purchase > 0 && arv > 0 && (
            <View style={styles.dealRuleCard}>
              <Text style={styles.dealRuleTitle}>70% Rule Check</Text>
              <Text style={styles.dealRuleDesc}>
                Max offer: {fmt(arv * 0.7 - rehab)} · Your offer: {fmt(purchase)}
              </Text>
              <View style={[
                styles.dealRuleBadge,
                purchase <= arv * 0.7 - rehab
                  ? { backgroundColor: Colors.success + '22', borderColor: Colors.success }
                  : { backgroundColor: Colors.danger + '22', borderColor: Colors.danger }
              ]}>
                <Ionicons
                  name={purchase <= arv * 0.7 - rehab ? 'checkmark-circle' : 'close-circle'}
                  size={16}
                  color={purchase <= arv * 0.7 - rehab ? Colors.success : Colors.danger}
                />
                <Text style={[
                  styles.dealRuleBadgeText,
                  { color: purchase <= arv * 0.7 - rehab ? Colors.success : Colors.danger }
                ]}>
                  {purchase <= arv * 0.7 - rehab ? 'Passes 70% Rule' : 'Fails 70% Rule'}
                </Text>
              </View>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function InputRow({
  label, value, onChange, prefix, suffix, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void;
  prefix?: string; suffix?: string; placeholder?: string;
}) {
  return (
    <View style={styles.inputRow}>
      <Text style={styles.inputLabel}>{label}</Text>
      <View style={styles.inputWrap}>
        {prefix && <Text style={styles.inputAddon}>{prefix}</Text>}
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={onChange}
          keyboardType="decimal-pad"
          placeholder={placeholder || '0'}
          placeholderTextColor={Colors.textMuted}
        />
        {suffix && <Text style={styles.inputAddon}>{suffix}</Text>}
      </View>
    </View>
  );
}

function ResultRow({
  label, value, color, large,
}: {
  label: string; value: string; color?: string; large?: boolean;
}) {
  return (
    <View style={[styles.resultRow, large && styles.resultRowLarge]}>
      <Text style={[styles.resultLabel, large && styles.resultLabelLarge]}>{label}</Text>
      <Text style={[styles.resultValue, { color: color || Colors.textPrimary }, large && styles.resultValueLarge]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
  },
  title: { ...Typography.h2, color: Colors.textPrimary },
  clearBtn: { padding: 8 },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  stratRow: { flexDirection: 'row', gap: Spacing.xs, marginBottom: Spacing.lg, flexWrap: 'wrap' },
  stratChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: Spacing.sm, paddingVertical: 7,
    borderRadius: Radii.full, borderWidth: 1.5, borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  stratLabel: { fontSize: 11, fontWeight: '700', color: Colors.textMuted },
  inputsCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border, overflow: 'hidden', marginBottom: Spacing.lg,
  },
  inputRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  inputLabel: { ...Typography.bodySmall, color: Colors.textSecondary, flex: 1, marginRight: Spacing.sm },
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  inputAddon: { ...Typography.bodySmall, color: Colors.textMuted },
  input: {
    ...Typography.bodySmall, color: Colors.textPrimary, textAlign: 'right',
    minWidth: 90, paddingVertical: 2,
  },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md },
  resultsCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border, overflow: 'hidden', marginBottom: Spacing.lg,
  },
  resultRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.md, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  resultRowLarge: { paddingVertical: 16, backgroundColor: Colors.surfaceElevated },
  resultLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  resultLabelLarge: { color: Colors.textPrimary, fontWeight: '600' },
  resultValue: { ...Typography.bodySmall, fontWeight: '700' },
  resultValueLarge: { fontSize: 20, fontWeight: '800' },
  dealRuleCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  dealRuleTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', marginBottom: 4 },
  dealRuleDesc: { ...Typography.caption, color: Colors.textMuted, marginBottom: Spacing.sm },
  dealRuleBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: Radii.md,
    paddingHorizontal: Spacing.md, paddingVertical: 8, borderWidth: 1, alignSelf: 'flex-start',
  },
  dealRuleBadgeText: { ...Typography.bodySmall, fontWeight: '700' },
});
