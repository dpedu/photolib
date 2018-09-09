module.exports = function(grunt) {
  grunt.initConfig({
    less: {
      website: {
        files: {
          'styles/css/main.css': 'styles/less/main.less'
        }
      }
    },
    cssmin: {
      website: {
        files: {
          'styles/mincss/pure.css': 'node_modules/purecss/build/pure.css',
          'styles/mincss/grids-responsive-min.css': 'node_modules/purecss/build/grids-responsive.css',
          'styles/mincss/main.css': 'styles/css/main.css'
        }
      }
    },
    concat: {
      dist: {
        src: [
          'styles/mincss/pure.css',
          'styles/mincss/grids-responsive-min.css',
          'styles/mincss/main.css'
        ],
        dest: 'styles/dist/style.css',
      },
    },
    watch: {
      less: {
        files: ['styles/less/{,*/}*.less'],
        tasks: ['less:website', 'cssmin:website', 'concat:dist'],
        options: {
          spawn: false
        }
      }
    }
  });

  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-contrib-cssmin');
  grunt.loadNpmTasks('grunt-contrib-concat');

  grunt.registerTask('default', ['less:website', 'cssmin:website', 'concat:dist']);
};
