// Applied before first paint to avoid a flash of the wrong theme. Dark mode is
// opt-in: only an explicit stored preference activates it, so surfaces that are
// not yet dark-audited stay light for users who never toggled.
const THEME_BOOTSTRAP = `(function(){try{var isDark=localStorage.getItem('rezumi-theme')==='dark';var root=document.documentElement;root.classList.toggle('dark',isDark);root.style.colorScheme=isDark?'dark':'light';}catch(e){}})();`;

export function ThemeScript() {
  // Static, non-user string executed before hydration to prevent theme flash.
  return <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />;
}
