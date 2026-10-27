<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const activeContentTab = ref<string>('roleplay')
const activeComparisonTab = ref<string>('traditional')

function goToApp() {
  router.push('/my-words')
}

const contentTypes = [
  {
    id: 'roleplay',
    icon: 'mdi:theater-masks',
    title: 'Roleplay Scenarios',
    description: 'Practice words in realistic conversations',
    example: {
      title: 'Job Interview Role-play',
      content: `👤 Interviewer: "Can you describe your most significant accomplishment?"
👨 You: "I led a team that [use: pivotal, transformative, initiative]..."
💡 Hint: This word means "serving as a central point"`,
      highlight: 'pivotal'
    }
  },
  {
    id: 'clusters',
    icon: 'mdi:sitemap',
    title: 'Word Clusters',
    description: 'Discover semantic relationships',
    example: {
      title: 'Excellence & Achievement Cluster',
      content: `excellence
      ├─ pinnacle (highest point)
      ├─ zenith (peak)
      └─ acme (highest stage)

Nuance: "pinnacle" emphasizes reach, "zenith" emphasizes astronomy origin`,
      highlight: 'Semantic Network'
    }
  },
  {
    id: 'examples',
    icon: 'mdi:book-open-variant',
    title: 'Rich Examples',
    description: 'Real-world contextual sentences',
    example: {
      title: 'Learning "Ephemeral"',
      content: `Definition: Lasting for a very short time

📰 News: "Cherry blossoms are ephemeral, beautiful for mere weeks"
📖 Literature: "Life is ephemeral, a fleeting moment in eternity"
💼 Business: "Social media trends are often ephemeral in nature"
✍️ Academic: "The ephemeral nature of digital content poses archiving challenges"`,
      highlight: 'Multiple Contexts'
    }
  },
  {
    id: 'challenges',
    icon: 'mdi:lightning-bolt',
    title: 'Write Challenges',
    description: 'Create sentences and get AI feedback',
    example: {
      title: 'Challenge: Use "Serendipity"',
      content: `Your attempt:
"I found my book by serendipity when I walked into the library"

✅ AI Feedback:
- Correct usage!
- Consider: "found my book through serendipity" (more natural)
- Example variation: "By sheer serendipity, I discovered..."
- Related words to combine: "fate, fortune, providence"`,
      highlight: 'Real-time AI Feedback'
    }
  },
  {
    id: 'combos',
    icon: 'mdi:puzzle',
    title: 'Word Combos',
    description: 'Learn collocations and phrases',
    example: {
      title: 'Common Word Combinations',
      content: `abolish + policy ➜ "abolish the outdated policy"
abolish + discrimination ➜ "abolish discrimination"
abolish + slavery ➜ "abolish slavery" (historical)

🎯 Frequency: "abolish discrimination" (most common in academic texts)
📊 Context: Legal, political, historical documents`,
      highlight: 'Collocation Mastery'
    }
  },
  {
    id: 'bestOptions',
    icon: 'mdi:lightbulb-on',
    title: 'Best Options',
    description: 'AI chooses optimal learning path',
    example: {
      title: 'Personalized Content Queue',
      content: `Today's learning path for you:
1. [Roleplay] Business Negotiation (your weak area)
2. [Examples] "Pragmatic" in different industries
3. [Challenge] Write 3 sentences with "nuance"
4. [Cluster] Explore "Opinion vs Fact" words
5. 🎁 [Surprise Reward] Mini quiz = 50 XP`,
      highlight: 'Adaptive Learning'
    }
  }
]

const comparisonItems = [
  {
    id: 'traditional',
    title: '❌ Traditional Flashcard Apps',
    features: [
      '📋 Single definition shown',
      '🔄 Repetitive matching games',
      '😴 Boring (feels like homework)',
      '❌ No context provided',
      '⏸️ Passive learning only',
      '📚 Feels like a dictionary'
    ]
  },
  {
    id: 'vocab-master',
    title: '✨ Vocab Master (This App)',
    features: [
      '🎭 Roleplay conversations',
      '🧠 Semantic clusters & relationships',
      '🎮 Engaging & fun activities',
      '🌍 Real-world contextual examples',
      '✍️ Active writing & creation',
      '🎯 Smart, adaptive learning paths'
    ]
  }
]

const features = [
  {
    icon: 'mdi:robot',
    title: 'AI-Generated Content',
    description: 'Every word gets custom examples, scenarios, and challenges generated on-the-fly',
    color: 'from-blue-500 to-cyan-500'
  },
  {
    icon: 'mdi:brain',
    title: 'Semantic Intelligence',
    description: 'Understand not just words, but how they relate to each other',
    color: 'from-purple-500 to-pink-500'
  },
  {
    icon: 'mdi:gamepad-variant',
    title: 'Gamified Learning',
    description: 'Earn rewards, unlock achievements, never feel like studying',
    color: 'from-yellow-500 to-orange-500'
  },
  {
    icon: 'mdi:sparkles',
    title: 'Surprise Elements',
    description: 'Unexpected challenges and rewards keep learning fresh and exciting',
    color: 'from-green-500 to-emerald-500'
  }
]

const testimonials = [
  {
    name: 'Sarah M.',
    role: 'Student',
    text: 'Finally, learning vocabulary doesn\'t feel like a chore. The roleplay scenarios make it feel real.'
  },
  {
    name: 'James L.',
    role: 'Professional',
    text: 'I love how I can see words in context with real examples. It\'s nothing like other apps.'
  },
  {
    name: 'Emma R.',
    role: 'Language Enthusiast',
    text: 'The AI feedback on my writing is incredibly helpful. I\'m learning naturally, not memorizing.'
  }
]
</script>

<template>
  <div class="landing-page">
    <!-- Navbar -->
    <nav class="navbar">
      <div class="navbar-container">
        <div class="logo">
          <Icon icon="mdi:brain" width="28" height="28" />
          <span>Vocab Master</span>
        </div>
        <button class="btn btn-primary" @click="goToApp">
          Start Free
        </button>
      </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-container">
        <div class="hero-content">
          <div class="badge">🚀 The Next Generation of Vocabulary Learning</div>
          <h1 class="hero-title">
            Stop Learning Words.<br>
            <span class="gradient-text">Start Mastering Language.</span>
          </h1>
          <p class="hero-subtitle">
            AI-powered content generation that creates personalized roleplay scenarios, semantic clusters, writing challenges, and more—all tailored to YOUR words.
          </p>
          <div class="hero-cta">
            <button class="btn btn-primary btn-lg" @click="goToApp">
              <Icon icon="mdi:play-circle" width="20" height="20" />
              Experience The Difference
            </button>
            <button class="btn btn-secondary btn-lg">
              <Icon icon="mdi:video" width="20" height="20" />
              See How It Works
            </button>
          </div>
          <div class="hero-stats">
            <div class="stat">
              <Icon icon="mdi:check-circle" width="24" height="24" />
              <div>
                <div class="stat-number">6+</div>
                <div class="stat-label">Content Types</div>
              </div>
            </div>
            <div class="stat">
              <Icon icon="mdi:robot" width="24" height="24" />
              <div>
                <div class="stat-number">100% AI</div>
                <div class="stat-label">Auto-Generated</div>
              </div>
            </div>
            <div class="stat">
              <Icon icon="mdi:lightning-bolt" width="24" height="24" />
              <div>
                <div class="stat-number">0</div>
                <div class="stat-label">Boring Drills</div>
              </div>
            </div>
          </div>
        </div>
        <div class="hero-visual">
          <div class="visual-circle circle-1"></div>
          <div class="visual-circle circle-2"></div>
          <img src="/e02_no_bg.png" alt="Learning" class="hero-image img-1" />
          <img src="/diamons01.png" alt="Reward" class="hero-image img-2" />
        </div>
      </div>
    </section>

    <!-- The Problem & Solution -->
    <section class="problem-solution">
      <div class="ps-container">
        <h2 class="section-title">Why Other Apps Fail</h2>
        <p class="section-subtitle">Comparison shows why Vocab Master is different</p>

        <div class="comparison-tabs">
          <button
            v-for="item in comparisonItems"
            :key="item.id"
            :class="['tab', { active: activeComparisonTab === item.id }]"
            @click="activeComparisonTab = item.id"
          >
            {{ item.title }}
          </button>
        </div>

        <div class="comparison-content">
          <div v-show="activeComparisonTab === 'traditional'" class="comparison-item">
            <div class="features-list">
              <div v-for="(feature, idx) in comparisonItems[0].features" :key="idx" class="feature-item">
                {{ feature }}
              </div>
            </div>
          </div>
          <div v-show="activeComparisonTab === 'vocab-master'" class="comparison-item">
            <div class="features-list vocab-master-list">
              <div v-for="(feature, idx) in comparisonItems[1].features" :key="idx" class="feature-item">
                {{ feature }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Content Types Showcase -->
    <section class="content-showcase">
      <div class="showcase-container">
        <h2 class="section-title">The 6 Types of Generated Content</h2>
        <p class="section-subtitle">Every word gets personalized, multi-faceted learning</p>

        <div class="content-tabs">
          <button
            v-for="content in contentTypes"
            :key="content.id"
            :class="['content-tab', { active: activeContentTab === content.id }]"
            @click="activeContentTab = content.id"
          >
            <Icon :icon="content.icon" width="24" height="24" />
            {{ content.title }}
          </button>
        </div>

        <div class="content-display">
          <div v-for="content in contentTypes" :key="content.id">
            <div v-if="activeContentTab === content.id" class="content-card">
              <div class="content-header">
                <div>
                  <h3 class="content-title">{{ content.title }}</h3>
                  <p class="content-description">{{ content.description }}</p>
                </div>
                <Icon :icon="content.icon" width="40" height="40" class="content-icon" />
              </div>

              <div class="example-box">
                <div class="example-title">{{ content.example.title }}</div>
                <pre class="example-content">{{ content.example.content }}</pre>
                <div class="example-badge">{{ content.example.highlight }}</div>
              </div>

              <div class="benefit-icons">
                <div v-if="content.id === 'roleplay'" class="benefit">
                  <Icon icon="mdi:conversation" width="20" height="20" />
                  Real Conversations
                </div>
                <div v-if="content.id === 'clusters'" class="benefit">
                  <Icon icon="mdi:connection" width="20" height="20" />
                  Learn Relationships
                </div>
                <div v-if="content.id === 'examples'" class="benefit">
                  <Icon icon="mdi:earth" width="20" height="20" />
                  Real-World Context
                </div>
                <div v-if="content.id === 'challenges'" class="benefit">
                  <Icon icon="mdi:check-bold" width="20" height="20" />
                  Instant Feedback
                </div>
                <div v-if="content.id === 'combos'" class="benefit">
                  <Icon icon="mdi:link" width="20" height="20" />
                  Native Patterns
                </div>
                <div v-if="content.id === 'bestOptions'" class="benefit">
                  <Icon icon="mdi:target" width="20" height="20" />
                  Smart Paths
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Why It Works -->
    <section class="why-it-works">
      <div class="why-container">
        <h2 class="section-title">Why This Actually Works</h2>

        <div class="why-grid">
          <div class="why-card">
            <div class="why-number">1</div>
            <h3>AI Generates Everything</h3>
            <p>Add a word → AI instantly creates examples, scenarios, challenges, and more in seconds</p>
          </div>
          <div class="why-card">
            <div class="why-number">2</div>
            <h3>Multiple Learning Angles</h3>
            <p>See the same word from 6+ different perspectives (roleplay, clusters, combos, etc.)</p>
          </div>
          <div class="why-card">
            <div class="why-number">3</div>
            <h3>Active Learning Only</h3>
            <p>No passive memorization—you write, you roleplay, you create, you actively learn</p>
          </div>
          <div class="why-card">
            <div class="why-number">4</div>
            <h3>Never Boring</h3>
            <p>Surprise rewards, gamification, and variety mean you stay engaged every day</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Key Features -->
    <section class="key-features">
      <div class="features-container">
        <h2 class="section-title">What Makes Us Different</h2>

        <div class="features-grid">
          <div v-for="(feature, idx) in features" :key="idx" class="feature-card">
            <div class="feature-icon-wrapper" :class="`bg-gradient-${idx}`">
              <Icon :icon="feature.icon" width="36" height="36" />
            </div>
            <h3 class="feature-title">{{ feature.title }}</h3>
            <p class="feature-description">{{ feature.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Testimonials -->
    <section class="testimonials">
      <div class="testimonials-container">
        <h2 class="section-title">Real Stories from Real Learners</h2>

        <div class="testimonials-grid">
          <div v-for="testimonial in testimonials" :key="testimonial.name" class="testimonial-card">
            <div class="stars">⭐⭐⭐⭐⭐</div>
            <p class="testimonial-text">"{{ testimonial.text }}"</p>
            <div class="testimonial-author">
              <div class="author-avatar">{{ testimonial.name.charAt(0) }}</div>
              <div>
                <div class="author-name">{{ testimonial.name }}</div>
                <div class="author-role">{{ testimonial.role }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Final CTA -->
    <section class="final-cta">
      <div class="cta-container">
        <h2>Ready to Learn Words The Right Way?</h2>
        <p>Join learners who are ditching boring apps and mastering language through engagement.</p>
        <div class="cta-buttons">
          <button class="btn btn-primary btn-lg btn-cta" @click="goToApp">
            <Icon icon="mdi:rocket-launch" width="20" height="20" />
            Start Free Today
          </button>
          <button class="btn btn-secondary btn-lg">
            <Icon icon="mdi:help-circle" width="20" height="20" />
            Questions?
          </button>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-content">
          <div class="footer-section">
            <div class="footer-logo">
              <Icon icon="mdi:brain" width="24" height="24" />
              Vocab Master
            </div>
            <p>AI-powered vocabulary learning that actually works.</p>
          </div>
          <div class="footer-section">
            <h4>Product</h4>
            <ul>
              <li><a href="#">Features</a></li>
              <li><a href="#">How It Works</a></li>
              <li><a href="#">Pricing</a></li>
            </ul>
          </div>
          <div class="footer-section">
            <h4>Company</h4>
            <ul>
              <li><a href="#">About</a></li>
              <li><a href="#">Blog</a></li>
              <li><a href="#">Contact</a></li>
            </ul>
          </div>
          <div class="footer-section">
            <h4>Legal</h4>
            <ul>
              <li><a href="#">Privacy</a></li>
              <li><a href="#">Terms</a></li>
              <li><a href="#">Cookie Policy</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          <p>&copy; 2024 Vocab Master. All rights reserved. | Made with ❤️ for language learners.</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ─── General ─── */
.landing-page {
  overflow-x: hidden;
  background: #ffffff;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
}

/* ─── Navbar ─── */
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  padding: 1rem 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.navbar-container {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ─── Buttons ─── */
.btn {
  border: none;
  border-radius: 10px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  letter-spacing: -0.5px;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: white;
  color: #667eea;
  border: 2px solid #667eea;
}

.btn-secondary:hover {
  background: #f8f9ff;
}

.btn-lg {
  padding: 1rem 2rem;
  font-size: 1.1rem;
}

.btn-cta {
  font-size: 1.2rem;
  padding: 1.2rem 2.5rem;
}

/* ─── Badge ─── */
.badge {
  display: inline-block;
  background: #f0f4ff;
  color: #667eea;
  padding: 0.75rem 1.5rem;
  border-radius: 50px;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 1.5rem;
  letter-spacing: -0.3px;
}

/* ─── Hero Section ─── */
.hero {
  padding: 5rem 2rem;
  background: linear-gradient(135deg, #ffffff 0%, #f0f4ff 100%);
  position: relative;
  overflow: hidden;
}

.hero::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.hero-container {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: center;
  position: relative;
  z-index: 1;
}

.hero-title {
  font-size: 3.5rem;
  line-height: 1.15;
  margin-bottom: 1.5rem;
  color: #0f172a;
  font-weight: 900;
  letter-spacing: -1.5px;
}

.gradient-text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  font-size: 1.25rem;
  color: #475569;
  margin-bottom: 2rem;
  line-height: 1.7;
  max-width: 550px;
  font-weight: 500;
}

.hero-cta {
  display: flex;
  gap: 1rem;
  margin-bottom: 3rem;
  flex-wrap: wrap;
}

.hero-stats {
  display: flex;
  gap: 3rem;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 150px;
}

.stat svg {
  color: #667eea;
  flex-shrink: 0;
}

.stat-number {
  font-size: 1.5rem;
  font-weight: 800;
  color: #0f172a;
}

.stat-label {
  font-size: 0.85rem;
  color: #64748b;
  font-weight: 500;
}

/* ─── Hero Visual ─── */
.hero-visual {
  position: relative;
  height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.visual-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
}

.circle-1 {
  width: 350px;
  height: 350px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  top: 10%;
  right: 10%;
}

.circle-2 {
  width: 250px;
  height: 250px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  bottom: 5%;
  left: 5%;
}

.hero-image {
  position: absolute;
  max-width: 160px;
  filter: drop-shadow(0 12px 40px rgba(0, 0, 0, 0.15));
  animation: float 3s ease-in-out infinite;
}

.img-1 {
  top: 5%;
  right: 10%;
  animation-delay: 0s;
}

.img-2 {
  bottom: 10%;
  left: 15%;
  max-width: 140px;
  animation-delay: 0.8s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-25px);
  }
}

/* ─── Problem/Solution Section ─── */
.problem-solution {
  padding: 6rem 2rem;
  background: #0f172a;
  color: white;
}

.ps-container {
  max-width: 1400px;
  margin: 0 auto;
}

.comparison-tabs {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
  flex-wrap: wrap;
  justify-content: center;
}

.comparison-tabs .tab {
  padding: 1rem 2rem;
  background: transparent;
  border: 2px solid #475569;
  color: #cbd5e0;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;
}

.comparison-tabs .tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
  color: white;
}

.comparison-tabs .tab:hover {
  border-color: #667eea;
  color: white;
}

.comparison-content {
  margin-top: 2rem;
}

.comparison-item {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.features-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.feature-item {
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  font-size: 1.05rem;
  line-height: 1.6;
}

.vocab-master-list .feature-item {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-color: rgba(102, 126, 234, 0.3);
}

/* ─── Content Showcase ─── */
.content-showcase {
  padding: 6rem 2rem;
  background: #f8f9fa;
}

.showcase-container {
  max-width: 1400px;
  margin: 0 auto;
}

.section-title {
  font-size: 2.75rem;
  text-align: center;
  margin-bottom: 0.5rem;
  color: #0f172a;
  font-weight: 900;
  letter-spacing: -1px;
}

.section-subtitle {
  font-size: 1.1rem;
  text-align: center;
  color: #64748b;
  margin-bottom: 3rem;
  font-weight: 500;
}

.content-tabs {
  display: flex;
  gap: 0.75rem;
  margin: 2rem 0;
  flex-wrap: wrap;
  justify-content: center;
}

.content-tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.5rem;
  background: white;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  color: #64748b;
  transition: all 0.3s ease;
}

.content-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.content-tab:hover:not(.active) {
  border-color: #667eea;
  color: #667eea;
}

.content-display {
  margin-top: 3rem;
}

.content-card {
  background: white;
  border-radius: 16px;
  padding: 3rem;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
  animation: slideIn 0.4s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  gap: 1rem;
}

.content-title {
  font-size: 1.75rem;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 0.5rem;
}

.content-description {
  color: #64748b;
  font-weight: 500;
  font-size: 1.05rem;
}

.content-icon {
  color: #667eea;
  flex-shrink: 0;
}

.example-box {
  background: #f1f5f9;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 2rem;
  margin-bottom: 2rem;
  position: relative;
}

.example-title {
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 1rem;
  font-size: 1.1rem;
}

.example-content {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  font-size: 0.95rem;
  line-height: 1.7;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Monaco', 'Courier New', monospace;
  margin: 0;
}

.example-badge {
  display: inline-block;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0.5rem 1.2rem;
  border-radius: 50px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: 1rem;
}

.benefit-icons {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.benefit {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #f0f4ff;
  color: #667eea;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.95rem;
}

.benefit svg {
  flex-shrink: 0;
}

/* ─── Why It Works ─── */
.why-it-works {
  padding: 6rem 2rem;
  background: white;
}

.why-container {
  max-width: 1400px;
  margin: 0 auto;
}

.why-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
  margin-top: 3rem;
}

.why-card {
  padding: 2.5rem 2rem;
  background: linear-gradient(135deg, #f8f9fa 0%, #f0f4ff 100%);
  border: 2px solid #e2e8f0;
  border-radius: 16px;
  text-align: center;
  transition: all 0.3s ease;
  position: relative;
}

.why-card:hover {
  border-color: #667eea;
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
}

.why-number {
  font-size: 3.5rem;
  font-weight: 900;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 1rem;
}

.why-card h3 {
  font-size: 1.35rem;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 1rem;
}

.why-card p {
  color: #64748b;
  line-height: 1.7;
  font-weight: 500;
}

/* ─── Key Features ─── */
.key-features {
  padding: 6rem 2rem;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: white;
}

.features-container {
  max-width: 1400px;
  margin: 0 auto;
}

.key-features .section-title {
  color: white;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
  margin-top: 3rem;
}

.feature-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 2.5rem;
  border-radius: 16px;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.feature-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(102, 126, 234, 0.5);
  transform: translateY(-8px);
}

.feature-icon-wrapper {
  width: 70px;
  height: 70px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: 1.5rem;
}

.bg-gradient-0 {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.bg-gradient-1 {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.bg-gradient-2 {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.bg-gradient-3 {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.feature-title {
  font-size: 1.3rem;
  font-weight: 800;
  margin-bottom: 0.75rem;
  color: white;
}

.feature-description {
  color: #cbd5e0;
  line-height: 1.7;
  font-weight: 500;
}

/* ─── Testimonials ─── */
.testimonials {
  padding: 6rem 2rem;
  background: #f8f9fa;
}

.testimonials-container {
  max-width: 1400px;
  margin: 0 auto;
}

.testimonials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  margin-top: 3rem;
}

.testimonial-card {
  background: white;
  padding: 2.5rem;
  border-radius: 16px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  border-left: 4px solid #667eea;
}

.testimonial-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
}

.stars {
  font-size: 1.2rem;
  margin-bottom: 1rem;
}

.testimonial-text {
  font-size: 1.05rem;
  line-height: 1.7;
  color: #475569;
  margin-bottom: 1.5rem;
  font-weight: 500;
}

.testimonial-author {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.author-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.2rem;
}

.author-name {
  font-weight: 700;
  color: #0f172a;
}

.author-role {
  font-size: 0.9rem;
  color: #64748b;
}

/* ─── Final CTA ─── */
.final-cta {
  padding: 6rem 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-align: center;
  position: relative;
  overflow: hidden;
}

.final-cta::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.cta-container {
  max-width: 700px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.final-cta h2 {
  font-size: 2.75rem;
  margin-bottom: 1rem;
  font-weight: 900;
  letter-spacing: -1px;
}

.final-cta p {
  font-size: 1.2rem;
  margin-bottom: 2rem;
  opacity: 0.95;
  font-weight: 500;
}

.cta-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

/* ─── Footer ─── */
.footer {
  background: #0f172a;
  color: #cbd5e0;
  padding: 3rem 2rem 1.5rem;
}

.footer-container {
  max-width: 1400px;
  margin: 0 auto;
}

.footer-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.footer-logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-weight: 800;
  color: white;
  margin-bottom: 1rem;
  font-size: 1.2rem;
}

.footer-section p {
  font-weight: 500;
  line-height: 1.6;
}

.footer-section h4 {
  font-weight: 800;
  color: white;
  margin-bottom: 1rem;
}

.footer-section ul {
  list-style: none;
  padding: 0;
}

.footer-section ul li {
  margin-bottom: 0.75rem;
}

.footer-section a {
  color: #94a3b8;
  text-decoration: none;
  transition: color 0.3s ease;
  font-weight: 500;
}

.footer-section a:hover {
  color: #667eea;
}

.footer-bottom {
  border-top: 1px solid #1e293b;
  padding-top: 1.5rem;
  text-align: center;
  color: #64748b;
  font-weight: 500;
}

/* ─── Responsive ─── */
@media (max-width: 1024px) {
  .hero-container {
    grid-template-columns: 1fr;
    gap: 2rem;
  }

  .hero-title {
    font-size: 2.75rem;
  }

  .hero-visual {
    min-height: 350px;
  }

  .content-card {
    padding: 2rem;
  }

  .features-grid,
  .testimonials-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .navbar {
    padding: 1rem;
  }

  .hero {
    padding: 3rem 1rem;
  }

  .hero-title {
    font-size: 2rem;
  }

  .hero-subtitle {
    font-size: 1rem;
  }

  .hero-cta {
    flex-direction: column;
  }

  .btn {
    width: 100%;
    justify-content: center;
  }

  .section-title {
    font-size: 2rem;
  }

  .content-tabs {
    flex-direction: column;
  }

  .content-tab {
    width: 100%;
    justify-content: flex-start;
  }

  .comparison-tabs {
    flex-direction: column;
  }

  .comparison-tabs .tab {
    width: 100%;
  }

  .features-grid,
  .testimonials-grid,
  .features-list {
    grid-template-columns: 1fr;
  }

  .hero-stats {
    flex-direction: column;
    gap: 1.5rem;
  }

  .content-header {
    flex-direction: column;
  }

  .why-grid {
    grid-template-columns: 1fr;
  }

  .final-cta h2 {
    font-size: 1.75rem;
  }

  .final-cta p {
    font-size: 1rem;
  }

  .cta-buttons {
    flex-direction: column;
  }

  .cta-buttons .btn {
    width: 100%;
  }

  .hero,
  .problem-solution,
  .content-showcase,
  .why-it-works,
  .key-features,
  .testimonials,
  .final-cta {
    padding: 3rem 1rem;
  }

  .ps-container,
  .showcase-container,
  .why-container,
  .features-container,
  .testimonials-container {
    padding: 0;
  }
}

@media (max-width: 480px) {
  .hero-title {
    font-size: 1.75rem;
    line-height: 1.2;
  }

  .hero-subtitle {
    font-size: 0.95rem;
  }

  .section-title {
    font-size: 1.5rem;
  }

  .badge {
    font-size: 0.85rem;
    padding: 0.65rem 1.25rem;
  }

  .btn {
    padding: 0.65rem 1.25rem;
    font-size: 0.95rem;
  }

  .btn-lg {
    padding: 0.85rem 1.5rem;
  }

  .stat-number {
    font-size: 1.25rem;
  }

  .stat-label {
    font-size: 0.75rem;
  }

  .content-card {
    padding: 1.5rem;
  }

  .example-box {
    padding: 1rem;
  }

  .example-content {
    font-size: 0.85rem;
  }

  .feature-card {
    padding: 1.5rem;
  }

  .why-number {
    font-size: 2.5rem;
  }

  .why-card h3 {
    font-size: 1.1rem;
  }

  .final-cta h2 {
    font-size: 1.5rem;
  }
}
</style>
