const fs = require('fs');
const path = require('path');

const screensDir = path.join(__dirname, 'src', 'screens');
const componentsDir = path.join(__dirname, 'src', 'components');

const updateShadows = (dir) => {
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.js'));
    files.forEach(file => {
        const filePath = path.join(dir, file);
        let content = fs.readFileSync(filePath, 'utf8');
        
        let changed = false;
        
        // Match card-like shadows and elevations
        const oldContent = content;
        content = content.replace(/elevation:\s*[234],/g, 'elevation: 10,');
        content = content.replace(/shadowOpacity:\s*0\.0[456]/g, 'shadowOpacity: 0.18');
        content = content.replace(/shadowOpacity:\s*0\.1,/g, 'shadowOpacity: 0.18,');
        content = content.replace(/shadowOffset:\s*{\s*width:\s*0,\s*height:\s*[24]\s*}/g, 'shadowOffset: { width: 0, height: 10 }');
        
        if (content !== oldContent) {
            fs.writeFileSync(filePath, content, 'utf8');
            console.log(`Updated shadows in ${file}`);
        }
    });
};

updateShadows(screensDir);
updateShadows(componentsDir);
console.log('Done!');
