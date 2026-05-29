import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { api } from '../../services/api';

interface AdminUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  subscription: string;
  is_active: boolean;
  is_blocked: boolean;
  created_at: string;
  last_login: string;
  onboarding_complete: boolean;
}

const ROLE_COLORS: Record<string, string> = {
  loan_officer: Colors.blueprint,
  processor: Colors.softGlow,
  underwriter: Colors.info,
  borrower: Colors.success,
  admin: Colors.warning,
  executive: Colors.blueprint,
  platform_admin: Colors.blueprint,
  master_admin: Colors.blueprint,
};

const SUB_COLORS: Record<string, string> = {
  enterprise: Colors.blueprint,
  professional: Colors.info,
  starter: Colors.success,
  loan_officer: Colors.softGlow,
  free: Colors.steel,
};

export default function AdminUsersScreen() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchUsers = useCallback(async (pageNum: number, searchVal: string, replace: boolean) => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/admin/users', {
        params: { page: pageNum, per_page: 25, search: searchVal },
      });
      const { users: newUsers, total: t, pages: p } = res.data;
      setUsers(prev => replace ? newUsers : [...prev, ...newUsers]);
      setTotal(t);
      setPages(p);
      setPage(pageNum);
    } catch (err) {
      console.error('admin users error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(1, '', true); }, [fetchUsers]);

  const onSearchChange = (val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => fetchUsers(1, val, true), 400);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchUsers(1, search, true);
    setRefreshing(false);
  }, [fetchUsers, search]);

  const loadMore = () => {
    if (!loading && page < pages) fetchUsers(page + 1, search, false);
  };

  const formatDate = (raw: string) => {
    if (!raw || raw === 'None' || raw === 'null') return '—';
    try {
      return new Date(raw).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    } catch {
      return '—';
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>All Users</Text>
        <Text style={styles.count}>{total} total</Text>
      </View>

      {/* Search */}
      <View style={styles.searchBar}>
        <Ionicons name="search-outline" size={18} color={Colors.textMuted} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search name or email…"
          placeholderTextColor={Colors.textMuted}
          value={search}
          onChangeText={onSearchChange}
          autoCapitalize="none"
          autoCorrect={false}
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => onSearchChange('')}>
            <Ionicons name="close-circle" size={18} color={Colors.textMuted} />
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={users}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => <UserRow user={item} formatDate={formatDate} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Ionicons name="people-outline" size={40} color={Colors.textMuted} />
              <Text style={styles.emptyText}>No users found</Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          loading && page > 1 ? (
            <ActivityIndicator color={Colors.blueprint} style={{ margin: Spacing.lg }} />
          ) : null
        }
      />

      {loading && page === 1 && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator color={Colors.blueprint} size="large" />
        </View>
      )}
    </SafeAreaView>
  );
}

function UserRow({ user, formatDate }: { user: AdminUser; formatDate: (s: string) => string }) {
  const roleColor = ROLE_COLORS[user.role] || Colors.steel;
  const subColor = SUB_COLORS[user.subscription] || Colors.steel;
  const initials = user.full_name
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <View style={styles.row}>
      <View style={[styles.avatar, { backgroundColor: roleColor + '33' }]}>
        <Text style={[styles.avatarText, { color: roleColor }]}>{initials || '?'}</Text>
      </View>
      <View style={styles.rowContent}>
        <View style={styles.rowTop}>
          <Text style={styles.name} numberOfLines={1}>{user.full_name}</Text>
          {user.is_blocked && (
            <View style={styles.blockedBadge}>
              <Text style={styles.blockedText}>Blocked</Text>
            </View>
          )}
        </View>
        <Text style={styles.email} numberOfLines={1}>{user.email}</Text>
        <View style={styles.rowBadges}>
          <Badge label={user.role.replace(/_/g, ' ')} color={roleColor} />
          <Badge label={user.subscription || 'free'} color={subColor} />
          <Text style={styles.dateText}>Joined {formatDate(user.created_at)}</Text>
        </View>
      </View>
    </View>
  );
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  title: { ...Typography.h2, color: Colors.textPrimary },
  count: { ...Typography.caption, color: Colors.textMuted },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radii.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    ...Typography.body,
    color: Colors.textPrimary,
    padding: 0,
  },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl * 2, gap: Spacing.sm },
  row: {
    flexDirection: 'row',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    alignItems: 'flex-start',
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontWeight: '700', fontSize: 16 },
  rowContent: { flex: 1, gap: 3 },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  name: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  email: { ...Typography.caption, color: Colors.textMuted },
  rowBadges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, alignItems: 'center', marginTop: 2 },
  badge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  blockedBadge: {
    backgroundColor: '#EF444422',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: Radii.full,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  blockedText: { fontSize: 10, fontWeight: '700', color: '#EF4444' },
  dateText: { ...Typography.caption, color: Colors.textMuted, fontSize: 10 },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: Spacing.xl * 2, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background + 'CC',
  },
});
