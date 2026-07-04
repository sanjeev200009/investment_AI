const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, 'src');

const processDirectory = (dir, relativePathToComponents) => {
    const files = fs.readdirSync(dir);
    
    files.forEach(file => {
        const fullPath = path.join(dir, file);
        if (fs.statSync(fullPath).isDirectory()) {
            if (file !== 'components' && file !== 'screens' && file !== 'navigation') return;
            const newRelativePath = relativePathToComponents + '../components/';
            processDirectory(fullPath, file === 'components' ? './' : '../components/');
        } else if (file.endsWith('.js') && file !== 'TouchableTick.js') {
            let content = fs.readFileSync(fullPath, 'utf8');
            let changed = false;
            
            if (content.includes('<TouchableOpacity')) {
                // Ensure import exists
                if (!content.includes('import TouchableTick')) {
                    // Find the last react-native import or just put it after React
                    content = `import TouchableTick from '${relativePathToComponents}TouchableTick';\n` + content;
                }
                
                // Replace tags
                content = content.replace(/<TouchableOpacity/g, '<TouchableTick');
                content = content.replace(/<\/TouchableOpacity>/g, '</TouchableTick>');
                
                changed = true;
            }
            
            if (changed) {
                fs.writeFileSync(fullPath, content, 'utf8');
                console.log(`Updated ${file}`);
            }
        }
    });
};

processDirectory(srcDir, '../components/');
console.log('Done replacing Touchables!');
