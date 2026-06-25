const e = React.createElement;

function RavloAcademySafe() {
  const academy = window.RAVLO_ACADEMY || {};
  const userName = academy.userName || 'Member';
  const tier = academy.tier || 'academy';

  const styles = {
    page: {
      minHeight: '100vh',
      background: 'radial-gradient(circle at 70% -10%, rgba(58,92,122,.24), transparent 34%), linear-gradient(180deg,#0C1116,#11161C)',
      color: '#FFFFFF',
      fontFamily: 'DM Sans, Inter, Arial, sans-serif',
      padding: '28px'
    },
    shell: { maxWidth: '1180px', margin: '0 auto' },
    brand: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '28px' },
    mark: { width: '42px', height: '42px', borderRadius: '14px', border: '1px solid rgba(76,122,163,.45)', background: 'linear-gradient(135deg,rgba(58,92,122,.35),rgba(26,35,44,.9))', display: 'grid', placeItems: 'center', color: '#d9e7f4', fontSize: '22px', fontWeight: 800 },
    brandName: { letterSpacing: '3px', fontSize: '13px', fontWeight: 800 },
    brandSub: { letterSpacing: '3px', fontSize: '9px', color: '#6B7F93', marginTop: '2px' },
    hero: { border: '1px solid rgba(107,127,147,.22)', background: 'linear-gradient(180deg,rgba(26,35,44,.86),rgba(17,22,28,.78))', borderRadius: '26px', padding: '34px', marginBottom: '18px' },
    eyebrow: { fontSize: '11px', letterSpacing: '2.5px', textTransform: 'uppercase', color: '#88a6bf', fontWeight: 800, marginBottom: '12px' },
    title: { fontSize: 'clamp(36px,6vw,68px)', lineHeight: 1, letterSpacing: '-2px', margin: '0 0 16px' },
    copy: { color: '#A7A9AC', lineHeight: 1.7, maxWidth: '760px', margin: '0 0 24px' },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '14px' },
    card: { border: '1px solid rgba(107,127,147,.22)', background: 'rgba(26,35,44,.72)', borderRadius: '20px', padding: '20px' },
    cardTitle: { fontSize: '20px', margin: '0 0 8px' },
    cardCopy: { color: '#A7A9AC', lineHeight: 1.6, margin: 0 },
    button: { display: 'inline-block', padding: '12px 18px', borderRadius: '14px', background: 'linear-gradient(135deg,#4C7AA3,#3A5C7A)', color: '#FFFFFF', textDecoration: 'none', fontWeight: 800 }
  };

  const cards = [
    ['Career Paths', 'Investor, lending, Realtor, property management, contractor, and company training paths.'],
    ['Company Academy', 'A place for companies to onboard employees, assign training, and organize SOPs.'],
    ['AI Mentor', 'A future coaching layer for workflow practice, company knowledge, and guided learning.']
  ];

  return e('main', { style: styles.page },
    e('div', { style: styles.shell },
      e('div', { style: styles.brand },
        e('div', { style: styles.mark }, 'R'),
        e('div', null,
          e('div', { style: styles.brandName }, 'RAVLO'),
          e('div', { style: styles.brandSub }, 'ACADEMY')
        )
      ),
      e('section', { style: styles.hero },
        e('div', { style: styles.eyebrow }, 'Academy portal restored'),
        e('h1', { style: styles.title }, 'Build the people behind every real estate business.'),
        e('p', { style: styles.copy }, 'Welcome back, ' + userName + '. Academy is temporarily running in safe mode so the portal stays live while the full learning engine is repaired. Access: ' + String(tier).toUpperCase() + '.'),
        e('a', { href: '/academy', style: styles.button }, 'View Academy Overview')
      ),
      e('section', { style: styles.grid },
        cards.map(function(card) {
          return e('article', { key: card[0], style: styles.card },
            e('h2', { style: styles.cardTitle }, card[0]),
            e('p', { style: styles.cardCopy }, card[1])
          );
        })
      )
    )
  );
}

ReactDOM.createRoot(document.getElementById('ravlo-university-root')).render(e(RavloAcademySafe));
